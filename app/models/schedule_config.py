from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScheduleConfig(Base):
    """
    Configuración de monitoreo automático.
    Cada fila representa una URL que el sistema audita periódicamente.
    """
    __tablename__ = "schedule_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(nullable=False)
    interval_minutes: Mapped[int] = mapped_column(default=60)  # cada cuántos minutos ejecutar
    is_active: Mapped[bool] = mapped_column(default=True)     # pausar sin eliminar
    last_run_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_run_status: Mapped[Optional[str]] = mapped_column(nullable=True)  # success | error
    last_run_error: Mapped[Optional[str]] = mapped_column(nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
