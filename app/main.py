import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.db import create_all, engine
from app.routers import admin_products, auth, events, pages, recommendations
from app.scheduler.jobs import create_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started with jobs: %s", [j.id for j in scheduler.get_jobs()])
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="SmartReco", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(admin_products.router)
app.include_router(events.router)
app.include_router(recommendations.router)


@app.get("/health", tags=["ops"])
def health():
    """Liveness + dependency check: SQL reachable and vector store count."""
    status = {"status": "ok", "sql": "ok", "vector_store": "ok", "products_indexed": None}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        status["status"], status["sql"] = "degraded", f"error: {exc}"
    try:
        from app.services import vector_store

        status["products_indexed"] = vector_store.count()
    except Exception as exc:  # noqa: BLE001
        status["status"], status["vector_store"] = "degraded", f"error: {exc}"
    return status
