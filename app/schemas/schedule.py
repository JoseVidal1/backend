from datetime import datetime
from typing import Optional

from pydantic import BaseModel, HttpUrl, field_validator


class ScheduleCreateRequest(BaseModel):
    url: HttpUrl
    interval_minutes: int = 60

    @field_validator("interval_minutes")
    @classmethod
    def validate_interval(cls, v):
        if v < 1:
            raise ValueError("El intervalo mínimo es 1 minuto.")
        if v > 10080:
            raise ValueError("El intervalo máximo es 10080 minutos (1 semana).")
        return v


class ScheduleResponse(BaseModel):
    id: int
    url: str
    interval_minutes: int
    is_active: bool
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_error: Optional[str] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScheduleListResponse(BaseModel):
    items: list[ScheduleResponse]
    total: int


class ScheduleToggleResponse(BaseModel):
    id: int
    is_active: bool
    message: str
    next_run_at: Optional[datetime] = None
