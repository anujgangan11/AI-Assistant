from typing import Optional

import numpy as np
from mem0 import Memory
from mem0.configs.base import MemoryConfig
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.embeddings.configs import EmbedderConfig
from mem0.llms.configs import LlmConfig

_memory: Optional[Memory] = None

# nomic-embed-text produces 768-dim vectors
_EMBED_DIMS = 768


def _patch_mem0_extraction() -> None:
    # mem0 2.0.0 bug: local LLMs return extracted memories as ["text"] (list of
    # strings) instead of [{"text": "...", "event": "ADD"}] (list of dicts).
    # Normalise before mem0 tries to call .get("text") on each item.
    try:
        import mem0.memory.main as _m0
        _orig = _m0.Memory._add_to_vector_store

        def _patched(self, messages, processed_metadata, effective_filters, infer, **kwargs):
            import mem0.memory.main as _inner
            _orig_parse = _inner.json.loads

            def _normalising_loads(s, **kw):
                result = _orig_parse(s, **kw)
                if isinstance(result, dict) and "memory" in result:
                    result["memory"] = [
                        {"text": m, "event": "ADD"} if isinstance(m, str) else m
                        for m in result["memory"]
                    ]
                return result

            _inner.json.loads = _normalising_loads
            try:
                return _orig(self, messages, processed_metadata, effective_filters, infer, **kwargs)
            finally:
                _inner.json.loads = _orig_parse

        _m0.Memory._add_to_vector_store = _patched
    except Exception:
        pass


def _register_numpy_adapter() -> None:
    """Register a psycopg3 text dumper for numpy arrays.

    Mem0's pgvector backend passes raw numpy ndarrays to psycopg3 %s placeholders.
    The SQL already casts the value with ::vector, so dumping as text works fine.
    """
    try:
        import psycopg
        from psycopg.adapt import Dumper

        class NpNdarrayDumper(Dumper):
            def dump(self, obj: np.ndarray) -> bytes:
                return ("[" + ",".join(str(float(v)) for v in obj.flatten()) + "]").encode()

        psycopg.adapters.register_dumper(np.ndarray, NpNdarrayDumper)
    except Exception:
        pass


def get_memory() -> Memory:
    global _memory
    if _memory is None:
        _patch_mem0_extraction()
        _register_numpy_adapter()
        from src.config import settings

        config = MemoryConfig(
            vector_store=VectorStoreConfig(
                provider="pgvector",
                config={
                    "connection_string": settings.DATABASE_URL,
                    "collection_name": "mem0_memories",
                    "embedding_model_dims": _EMBED_DIMS,
                    "hnsw": True,
                },
            ),
            embedder=EmbedderConfig(
                provider="ollama",
                config={
                    "model": "nomic-embed-text",
                    "ollama_base_url": settings.OLLAMA_EMBED_URL,
                    "embedding_dims": _EMBED_DIMS,
                },
            ),
            llm=LlmConfig(
                provider="ollama",
                config={
                    "model": settings.OLLAMA_LLM_MODEL,
                    "ollama_base_url": settings.OLLAMA_LLM_URL,
                },
            ),
        )
        _memory = Memory(config=config)
    return _memory
