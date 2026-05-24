import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine, run_sqlite_migrations
import app.models  # noqa: F401 — registra todos los modelos en Base.metadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ciclo de vida de FastAPI:
    - Al arrancar: crea tablas, inicia scheduler y restaura jobs activos.
    - Al apagar: detiene scheduler limpiamente.
    """
    from app.services.scheduler import restore_active_schedules, start_scheduler

    Base.metadata.create_all(bind=engine)
    run_sqlite_migrations()
    logger.info("Tablas de la base de datos verificadas/creadas.")

    start_scheduler()

    # Restaurar schedules activos que estaban corriendo antes del reinicio
    db = SessionLocal()
    try:
        count = restore_active_schedules(db)
        if count:
            logger.info("%s schedule(s) restaurados desde DB.", count)
    finally:
        db.close()

    logger.info("GEO Copilot API iniciada correctamente.")
    yield

    # --- Shutdown ---
    from app.services.scheduler import stop_scheduler
    stop_scheduler()
    logger.info("GEO Copilot API detenida.")


app = FastAPI(
    title="GEO Copilot API",
    description=(
        "Backend Serfinanza — AUDITAR, RECOMENDAR, EDITAR y APRENDER "
        "para optimización en motores generativos (GEO)."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS: permite que el frontend en localhost:3000 llame a esta API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
from app.routers import admin, agent, analyze, gsc, probe, proposals, schedule

app.include_router(analyze.router)
app.include_router(probe.router)
app.include_router(gsc.router)
app.include_router(agent.router)
app.include_router(proposals.router)
app.include_router(schedule.router)
app.include_router(admin.router)


@app.get("/health", tags=["Sistema"])
def health_check():
    """Verifica que el servidor está corriendo."""
    return {"status": "ok"}
