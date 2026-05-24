from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class ScrapeResult(Base):
    __tablename__ = "scrape_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"), unique=True)

    title: Mapped[Optional[str]] = mapped_column(nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(nullable=True)
    h1: Mapped[Optional[str]] = mapped_column(nullable=True)
    h2_list_json: Mapped[Optional[str]] = mapped_column(nullable=True)  # JSON array serializado
    body_text: Mapped[Optional[str]] = mapped_column(nullable=True)     # máx 10k chars
    word_count: Mapped[int] = mapped_column(default=0)
    has_faq_schema: Mapped[bool] = mapped_column(default=False)
    has_structured_data: Mapped[bool] = mapped_column(default=False)    # cualquier ld+json
    images_without_alt: Mapped[int] = mapped_column(default=0)
    internal_links_count: Mapped[int] = mapped_column(default=0)
    scrape_warning: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    analysis: Mapped["Analysis"] = relationship(back_populates="scrape_result")
