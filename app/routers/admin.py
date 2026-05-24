"""
Endpoints administrativos — solo para desarrollo/demo.
NO exponer en producción real sin autenticación.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/reset", summary="Limpia todas las tablas de datos")
def reset_database(db: Session = Depends(get_db)):
    """
    Elimina TODOS los registros de análisis, propuestas, scrapes y probes.
    Conserva los schedules configurados.
    """
    tables = [
        "llm_probe_results",
        "scrape_results",
        "proposals",
        "analyses",
    ]
    deleted = {}
    for table in tables:
        try:
            result = db.execute(text(f"DELETE FROM {table}"))
            deleted[table] = result.rowcount
        except Exception as exc:
            logger.warning("No se pudo limpiar tabla %s: %s", table, exc)
            deleted[table] = f"error: {exc}"

    db.commit()
    logger.info("DB reset: %s", deleted)
    return {
        "status": "ok",
        "message": "Base de datos limpiada correctamente.",
        "deleted": deleted,
    }
