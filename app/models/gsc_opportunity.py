from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GSCOpportunity(Base):
    __tablename__ = "gsc_opportunities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(nullable=False)
    impressions: Mapped[int] = mapped_column(default=0)
    position: Mapped[float] = mapped_column(default=0.0)   # posición promedio en Google
    ctr: Mapped[float] = mapped_column(default=0.0)        # click-through rate 0.0-1.0
    imported_at: Mapped[datetime] = mapped_column(default=func.now())
