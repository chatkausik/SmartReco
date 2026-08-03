import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.db import create_all, engine
from app.routers import admin_products, admin_signals, auth, events, mesh, pages, recommendations
from app.scheduler.jobs import create_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _bootstrap_if_empty() -> None:
    """For cloud deploys (ephemeral disk): bootstrap the admin + seed the catalog when the
    products table is empty, so a fresh instance comes up usable. Opt-in via AUTO_SEED_ON_STARTUP.
    Seeding embeds through Mesh, so a funded MESH_API_KEY is required; failures are logged, not fatal.
    """
    from sqlalchemy import func, select

    from app.db import SessionLocal
    from app.models.product import Product

    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(Product)) or 0
    if count:
        logger.info("Startup seed skipped: %d products already present", count)
        return
    logger.info("AUTO_SEED_ON_STARTUP: empty catalog — bootstrapping admin + seeding products")
    try:
        from scripts.init_db import main as init_admin
        from scripts.seed_products import main as seed_products

        init_admin()
        seed_products()
    except Exception:
        logger.exception("Startup seeding failed (is MESH_API_KEY funded?) — app still starts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all()
    if settings.auto_seed_on_startup:
        _bootstrap_if_empty()
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started with jobs: %s", [j.id for j in scheduler.get_jobs()])
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="SmartReco", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def ensure_session_cookie(request: Request, call_next):
    """Give every browser a stable sr_sid so anonymous behavioral events can be tied back to
    the same visitor (used to seed the Your Signal panel and co-view relations)."""
    sid = request.cookies.get("sr_sid")
    is_new = sid is None
    if is_new:
        sid = uuid.uuid4().hex
    request.state.sr_sid = sid
    response = await call_next(request)
    if is_new:
        response.set_cookie("sr_sid", sid, max_age=60 * 60 * 24 * 180, samesite="lax")
    return response


app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(admin_products.router)
app.include_router(admin_signals.router)
app.include_router(events.router)
app.include_router(recommendations.router)
app.include_router(mesh.router)


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
