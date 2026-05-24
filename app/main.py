import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine, run_sqlite_migrations
import app.models  # noqa: F401 — registra todos los modelos en Base.metadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GEO Copilot API",
    description=(
        "Backend Serfinanza — AUDITAR, RECOMENDAR, EDITAR y APRENDER "
        "para optimización en motores generativos (GEO)."
    ),
    version="2.0.0",
)

# CORS: permite que el frontend en localhost:3000 llame a esta API.
# allow_origins: lista de dominios permitidos.
# allow_methods=["*"]: acepta GET, POST, PUT, DELETE, etc.
# allow_headers=["*"]: acepta cualquier header (necesario para Content-Type, Authorization).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crea las tablas en la DB si no existen todavía.
# En producción usaríamos Alembic para migraciones, pero para el hackathon esto es suficiente.
Base.metadata.create_all(bind=engine)
run_sqlite_migrations()
logger.info("Tablas de la base de datos verificadas/creadas.")

# --- Routers ---
from app.routers import agent, analyze, gsc, probe, proposals

app.include_router(analyze.router)
app.include_router(probe.router)
app.include_router(gsc.router)
app.include_router(agent.router)
app.include_router(proposals.router)


@app.get("/health", tags=["Sistema"])
def health_check():
    """Verifica que el servidor está corriendo."""
    return {"status": "ok"}


logger.info("GEO Copilot API iniciada correctamente.")
