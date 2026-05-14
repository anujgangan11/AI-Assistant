import logging

from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.db.connection import get_pool, close_pool
from src.gateway.whatsapp import router as whatsapp_router

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


app = FastAPI(title="AI Assistant Gateway", lifespan=lifespan)
app.include_router(whatsapp_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
