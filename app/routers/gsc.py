import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analysis import Analysis
from app.models.gsc_opportunity import GSCOpportunity
from app.models.scrape_result import ScrapeResult
from app.schemas.gsc import GSCOpportunityListResponse, GSCOpportunitySchema
from app.services.gsc_mock import GSC_MOCK_OPPORTUNITIES
from app.services.query_discovery import discover_queries, extract_seeds
from app.services.scraper import ScrapeData

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gsc", tags=["Auditar - GSC"])


def _ensure_gsc_seed(db: Session) -> None:
    """Si la tabla está vacía, siembra datos del mock (útil sin correr init_db)."""
    if db.query(GSCOpportunity).count() > 0:
        return
    for row in GSC_MOCK_OPPORTUNITIES:
        db.add(GSCOpportunity(**row))
    db.commit()
    logger.info("GSC mock sembrado en DB (%s filas).", len(GSC_MOCK_OPPORTUNITIES))


@router.get("/opportunities", response_model=GSCOpportunityListResponse)
def list_gsc_opportunities(db: Session = Depends(get_db)):
    """
    Lista oportunidades de búsqueda detectadas.
    Si se corrió `/agent/run-full-cycle`, muestra queries reales descubiertas
    con Google Suggest y DuckDuckGo basadas en el contenido del sitio.
    Si no, muestra datos representativos del mercado financiero colombiano.
    """
    _ensure_gsc_seed(db)
    rows = db.query(GSCOpportunity).order_by(GSCOpportunity.impressions.desc()).all()
    return GSCOpportunityListResponse(
        items=[GSCOpportunitySchema.model_validate(r) for r in rows],
        total=len(rows),
    )


class DiscoverRequest(BaseModel):
    analysis_id: int


@router.post("/discover", response_model=GSCOpportunityListResponse)
def discover_gsc_opportunities(body: DiscoverRequest, db: Session = Depends(get_db)):
    """
    Descubre queries reales para un análisis existente usando
    Google Suggest + DuckDuckGo Autocomplete (sin API key).
    Reemplaza las oportunidades GSC actuales con los resultados.
    """
    import json

    analysis = db.get(Analysis, body.analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"No existe análisis con id {body.analysis_id}.")

    scrape = db.query(ScrapeResult).filter(ScrapeResult.analysis_id == body.analysis_id).one_or_none()
    if not scrape:
        raise HTTPException(status_code=400, detail="El análisis no tiene datos de scrape.")

    h2_list = []
    if scrape.h2_list_json:
        try:
            h2_list = json.loads(scrape.h2_list_json)
        except Exception:
            pass

    scrape_data = ScrapeData(
        url=analysis.url,
        title=scrape.title or "",
        h1=scrape.h1 or "",
        h2_list=h2_list,
        body_text=scrape.body_text or "",
        word_count=scrape.word_count or 0,
    )

    seeds = extract_seeds(scrape_data)
    discovered = discover_queries(seeds)

    if not discovered:
        raise HTTPException(
            status_code=503,
            detail="No se pudieron descubrir queries. Verifica la conexión a internet.",
        )

    # Reemplazar oportunidades en DB
    db.query(GSCOpportunity).delete()
    for row in discovered:
        db.add(GSCOpportunity(**row))
    db.commit()

    rows = db.query(GSCOpportunity).order_by(GSCOpportunity.impressions.desc()).all()
    logger.info("GSC discover: %s queries guardadas para analysis_id=%s", len(rows), body.analysis_id)

    return GSCOpportunityListResponse(
        items=[GSCOpportunitySchema.model_validate(r) for r in rows],
        total=len(rows),
    )
