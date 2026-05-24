import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.enums import ProposalStatus, ProposalType
from app.models.proposal import Proposal, ProposalFeedback
from app.schemas.proposal import (
    ProposalApproveResponse,
    ProposalDetail,
    ProposalListResponse,
    ProposalRejectResponse,
    ProposalSummary,
    RejectRequest,
    MeasureImpactResponse,
)
from app.services.impact_mock import measure_proposal_impact
from app.services.content_utils import clean_gemini_output
from app.services.wordpress_adapter import publish_proposal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proposals", tags=["Editar"])


@router.get("", response_model=ProposalListResponse)
def list_proposals(
    status: ProposalStatus | None = None,
    proposal_type: ProposalType | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Lista propuestas con filtros opcionales."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit debe estar entre 1 y 100.")
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset no puede ser negativo.")

    query = db.query(Proposal)
    if status is not None:
        query = query.filter(Proposal.status == status.value)
    if proposal_type is not None:
        query = query.filter(Proposal.proposal_type == proposal_type.value)

    total = query.count()
    rows = (
        query.order_by(Proposal.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return ProposalListResponse(
        items=[ProposalSummary.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{proposal_id}", response_model=ProposalDetail)
def get_proposal(proposal_id: int, db: Session = Depends(get_db)):
    """Detalle de una propuesta con feedback e impact measurements."""
    proposal = (
        db.query(Proposal)
        .options(
            joinedload(Proposal.feedbacks),
            joinedload(Proposal.impact_measurements),
        )
        .filter(Proposal.id == proposal_id)
        .one_or_none()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail=f"No existe propuesta con id {proposal_id}.")

    return ProposalDetail.model_validate(proposal)


@router.post("/{proposal_id}/approve", response_model=ProposalApproveResponse)
def approve_proposal(proposal_id: int, db: Session = Depends(get_db)):
    """
    Aprueba una propuesta pendiente y la publica en WordPress (real si hay credenciales en .env).
    """
    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"No existe propuesta con id {proposal_id}.")

    if proposal.status != ProposalStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail=f"Solo se pueden aprobar propuestas pendientes (estado actual: {proposal.status}).",
        )

    proposal.content = clean_gemini_output(proposal.content or "")

    try:
        wp_result = publish_proposal(
            proposal_type=proposal.proposal_type,
            title=proposal.title,
            content=proposal.content,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    proposal.status = ProposalStatus.APPROVED.value
    proposal.wp_published_url = wp_result.get("url")
    proposal.wp_published_id = wp_result.get("id")
    proposal.reviewed_at = datetime.now()
    db.commit()
    db.refresh(proposal)

    logger.info("Propuesta %s aprobada → %s", proposal_id, proposal.wp_published_url)

    return ProposalApproveResponse(
        id=proposal.id,
        status=ProposalStatus(proposal.status),
        wp_published_url=proposal.wp_published_url,
        wp_published_id=proposal.wp_published_id,
        reviewed_at=proposal.reviewed_at,
    )


@router.post("/{proposal_id}/reject", response_model=ProposalRejectResponse)
def reject_proposal(
    proposal_id: int,
    body: RejectRequest,
    db: Session = Depends(get_db),
):
    """
    Rechaza una propuesta con motivo. Guarda feedback para el verbo APRENDER.
    """
    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"No existe propuesta con id {proposal_id}.")

    if proposal.status != ProposalStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail=f"Solo se pueden rechazar propuestas pendientes (estado actual: {proposal.status}).",
        )

    feedback = ProposalFeedback(proposal_id=proposal.id, reason=body.reason)
    proposal.status = ProposalStatus.REJECTED.value
    proposal.reviewed_at = datetime.now()

    db.add(feedback)
    db.commit()
    db.refresh(proposal)
    db.refresh(feedback)

    logger.info("Propuesta %s rechazada: %s", proposal_id, body.reason[:80])

    return ProposalRejectResponse(
        id=proposal.id,
        status=ProposalStatus(proposal.status),
        feedback_id=feedback.id,
        reviewed_at=proposal.reviewed_at,
    )


@router.post("/{proposal_id}/measure-impact", response_model=MeasureImpactResponse)
def measure_impact(proposal_id: int, db: Session = Depends(get_db)):
    """Simula re-medición a 4 semanas (verbo APRENDER)."""
    return measure_proposal_impact(proposal_id, db)
