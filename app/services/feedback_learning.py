"""Recupera aprendizajes de rechazos para mejorar prompts futuros (verbo APRENDER)."""

import logging

from sqlalchemy.orm import Session

from app.models.proposal import ProposalFeedback

logger = logging.getLogger(__name__)

DEFAULT_LEARNING_LIMIT = 15


def get_rejection_learnings(db: Session, limit: int = DEFAULT_LEARNING_LIMIT) -> list[str]:
    """
    Devuelve motivos de rechazo recientes para inyectar en prompts de Gemini.
    Así la IA evita repetir errores señalados por revisores humanos.
    """
    rows = (
        db.query(ProposalFeedback)
        .order_by(ProposalFeedback.created_at.desc())
        .limit(limit)
        .all()
    )
    reasons = [r.reason.strip() for r in rows if r.reason and r.reason.strip()]
    if reasons:
        logger.info("Inyectando %s aprendizajes de rechazos en prompts", len(reasons))
    return reasons
