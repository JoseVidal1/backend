from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # nullable: una propuesta puede venir de probe sin tener un análisis de URL
    analysis_id: Mapped[Optional[int]] = mapped_column(ForeignKey("analyses.id"), nullable=True)

    # Tipo: BLOG_POST | META_DESCRIPTION | FAQ_SCHEMA | ALT_TEXT_FIX | SCHEMA_MARKUP | GEO_INSIGHT
    proposal_type: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(nullable=True)   # resumen para card del dashboard
    content: Mapped[Optional[str]] = mapped_column(nullable=True)   # HTML/markdown/JSON completo

    # high | medium | low
    severity: Mapped[str] = mapped_column(default="medium")
    # scrape | llm_probe | gsc
    trigger_source: Mapped[str] = mapped_column(nullable=False)
    trigger_query: Mapped[Optional[str]] = mapped_column(nullable=True)

    # pending | approved | rejected
    status: Mapped[str] = mapped_column(default="pending")

    # datos devueltos por el WordPress mock al aprobar
    wp_published_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    wp_published_id: Mapped[Optional[int]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    analysis: Mapped[Optional["Analysis"]] = relationship(back_populates="proposals")
    feedbacks: Mapped[list["ProposalFeedback"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )
    impact_measurements: Mapped[list["ImpactMeasurement"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )


class ProposalFeedback(Base):
    __tablename__ = "proposal_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"))
    reason: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    proposal: Mapped["Proposal"] = relationship(back_populates="feedbacks")


class ImpactMeasurement(Base):
    __tablename__ = "impact_measurements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"))
    llm_mentioned_after: Mapped[bool] = mapped_column(default=False)
    similarity_score_after: Mapped[float] = mapped_column(default=0.0)
    google_position_after: Mapped[float] = mapped_column(default=0.0)
    measured_at: Mapped[datetime] = mapped_column(default=func.now())

    proposal: Mapped["Proposal"] = relationship(back_populates="impact_measurements")
