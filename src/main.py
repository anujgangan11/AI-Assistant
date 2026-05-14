import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db.connection import close_pool, get_pool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — warming DB pool")
    await get_pool()
    yield
    logger.info("Shutting down — closing DB pool")
    await close_pool()


app = FastAPI(title="AI Assistant", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
