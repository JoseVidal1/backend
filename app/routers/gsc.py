import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.gsc_opportunity import GSCOpportunity
from app.schemas.gsc import GSCOpportunityListResponse, GSCOpportunitySchema
from app.services.gsc_mock import GSC_MOCK_OPPORTUNITIES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gsc", tags=["Auditar - GSC Mock"])


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
    """Lista oportunidades mockeadas de Google Search Console."""
    _ensure_gsc_seed(db)
    rows = db.query(GSCOpportunity).order_by(GSCOpportunity.impressions.desc()).all()
    return GSCOpportunityListResponse(
        items=[GSCOpportunitySchema.model_validate(r) for r in rows],
        total=len(rows),
    )
