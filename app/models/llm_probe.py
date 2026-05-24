from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class LLMProbeResult(Base):
    __tablename__ = "llm_probe_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # nullable: el probe puede correrse sin estar ligado a un análisis de URL
    analysis_id: Mapped[Optional[int]] = mapped_column(ForeignKey("analyses.id"), nullable=True)

    query: Mapped[str] = mapped_column(nullable=False)
    llm_response_excerpt: Mapped[Optional[str]] = mapped_column(nullable=True)  # primeros 500 chars
    serfinanza_mentioned: Mapped[bool] = mapped_column(default=False)
    competitors_mentioned_json: Mapped[Optional[str]] = mapped_column(nullable=True)  # JSON array
    similarity_score: Mapped[float] = mapped_column(default=0.0)   # 0.0-1.0, dado por Gemini-judge
    needs_content: Mapped[bool] = mapped_column(default=True)      # True si NO mencionó Serfinanza
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    analysis: Mapped[Optional["Analysis"]] = relationship(back_populates="llm_probe_results")
