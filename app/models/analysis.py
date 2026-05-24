from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.scrape_result import ScrapeResult
    from app.models.proposal import Proposal
    from app.models.llm_probe import LLMProbeResult


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(nullable=False)
    seo_score: Mapped[Optional[int]] = mapped_column(nullable=True)
    geo_score: Mapped[Optional[int]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default="pending")
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    scrape_result: Mapped[Optional["ScrapeResult"]] = relationship(
        back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )
    proposals: Mapped[list["Proposal"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    llm_probe_results: Mapped[list["LLMProbeResult"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
