import logging
import random

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.enums import TriggerSource
from app.models.llm_probe import LLMProbeResult
from app.models.proposal import ImpactMeasurement, Proposal
from app.schemas.proposal import ImpactMeasurementSchema, MeasureImpactResponse

logger = logging.getLogger(__name__)


def measure_proposal_impact(proposal_id: int, db: Session) -> MeasureImpactResponse:
    """
    Simula re-medición a 4 semanas (mock APRENDER).
    Si Serfinanza no era mencionada, ahora lo es ~70% de las veces.
    """
    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"No existe propuesta con id {proposal_id}.")

    base_similarity = 0.2
    was_mentioned = False

    if proposal.analysis_id and proposal.trigger_source == TriggerSource.LLM_PROBE.value:
        probe = (
            db.query(LLMProbeResult)
            .filter(
                LLMProbeResult.analysis_id == proposal.analysis_id,
                LLMProbeResult.query == proposal.trigger_query,
            )
            .order_by(LLMProbeResult.created_at.desc())
            .first()
        )
        if probe:
            base_similarity = probe.similarity_score
            was_mentioned = probe.serfinanza_mentioned

    if was_mentioned:
        llm_mentioned_after = True
    else:
        llm_mentioned_after = random.random() < 0.7

    similarity_after = round(min(1.0, base_similarity + random.uniform(0.1, 0.3)), 2)
    position_after = round(random.uniform(8.0, 25.0), 1)

    measurement = ImpactMeasurement(
        proposal_id=proposal.id,
        llm_mentioned_after=llm_mentioned_after,
        similarity_score_after=similarity_after,
        google_position_after=position_after,
    )
    db.add(measurement)
    db.commit()
    db.refresh(measurement)

    if llm_mentioned_after and not was_mentioned:
        summary = (
            f"Mejora simulada: Serfinanza ahora es mencionada por el LLM. "
            f"Similitud subió de {base_similarity:.2f} a {similarity_after:.2f}. "
            f"Posición Google estimada: {position_after}."
        )
    elif llm_mentioned_after:
        summary = (
            f"Serfinanza sigue siendo mencionada. Similitud: {similarity_after:.2f}. "
            f"Posición Google: {position_after}."
        )
    else:
        summary = (
            f"Aún sin mención de Serfinanza. Similitud mejoró a {similarity_after:.2f}. "
            f"Se recomienda publicar más contenido GEO."
        )

    logger.info("Impact measurement mock para propuesta %s", proposal_id)

    return MeasureImpactResponse(
        proposal_id=proposal.id,
        measurement=ImpactMeasurementSchema.model_validate(measurement),
        improvement_summary=summary,
    )
