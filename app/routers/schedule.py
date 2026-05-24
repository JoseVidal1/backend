import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schedule_config import ScheduleConfig
from app.schemas.schedule import (
    ScheduleCreateRequest,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleToggleResponse,
)
from app.services import scheduler as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent/schedules", tags=["Automatización"])


@router.post("", response_model=ScheduleResponse, status_code=201)
def create_schedule(body: ScheduleCreateRequest, db: Session = Depends(get_db)):
    """
    Crea un monitoreo automático para una URL.
    El sistema ejecutará el ciclo completo (scrape + probe + propuestas)
    cada `interval_hours` horas de forma automática.

    - **interval_hours**: entre 1 y 168 (1 semana). Default: 24h.
    """
    url = str(body.url)

    # Evitar duplicados de la misma URL
    existing = (
        db.query(ScheduleConfig)
        .filter(ScheduleConfig.url == url)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Ya existe un schedule para esta URL (id={existing.id}). "
                   f"Usa PATCH /agent/schedules/{existing.id} para modificarlo.",
        )

    config = ScheduleConfig(
        url=url,
        interval_minutes=body.interval_minutes,
        is_active=True,
    )
    db.add(config)
    db.flush()  # obtenemos el id antes de commit

    next_run = svc.add_job(config.id, url, body.interval_minutes)
    config.next_run_at = next_run
    db.commit()
    db.refresh(config)

    logger.info("Schedule creado id=%s url=%s cada %smin", config.id, url, body.interval_minutes)
    return ScheduleResponse.model_validate(config)


@router.get("", response_model=ScheduleListResponse)
def list_schedules(db: Session = Depends(get_db)):
    """Lista todos los schedules activos e inactivos con su próxima ejecución."""
    rows = db.query(ScheduleConfig).order_by(ScheduleConfig.created_at.desc()).all()

    # Sincronizar next_run_at con el estado real del scheduler
    for row in rows:
        if row.is_active:
            row.next_run_at = svc.get_next_run(row.id)

    return ScheduleListResponse(
        items=[ScheduleResponse.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("/{schedule_id}/pause", response_model=ScheduleToggleResponse)
def pause_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Pausa un schedule sin eliminarlo. Se puede reactivar después."""
    config = db.get(ScheduleConfig, schedule_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"No existe schedule con id {schedule_id}.")
    if not config.is_active:
        raise HTTPException(status_code=400, detail="El schedule ya está pausado.")

    svc.pause_job(schedule_id)
    config.is_active = False
    config.next_run_at = None
    db.commit()

    logger.info("Schedule pausado id=%s", schedule_id)
    return ScheduleToggleResponse(
        id=schedule_id,
        is_active=False,
        message=f"Schedule pausado. El ciclo para '{config.url}' no se ejecutará hasta que lo reactives.",
    )


@router.post("/{schedule_id}/resume", response_model=ScheduleToggleResponse)
def resume_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Reactiva un schedule pausado."""
    config = db.get(ScheduleConfig, schedule_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"No existe schedule con id {schedule_id}.")
    if config.is_active:
        raise HTTPException(status_code=400, detail="El schedule ya está activo.")

    next_run = svc.resume_job(schedule_id, config.url, config.interval_minutes)
    config.is_active = True
    config.next_run_at = next_run
    db.commit()

    logger.info("Schedule reactivado id=%s próxima=%s", schedule_id, next_run)
    return ScheduleToggleResponse(
        id=schedule_id,
        is_active=True,
        message=f"Schedule reactivado. Próxima ejecución: {next_run.strftime('%Y-%m-%d %H:%M')}",
        next_run_at=next_run,
    )


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Elimina permanentemente un schedule y cancela su job."""
    config = db.get(ScheduleConfig, schedule_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"No existe schedule con id {schedule_id}.")

    svc.remove_job(schedule_id)
    db.delete(config)
    db.commit()

    logger.info("Schedule eliminado id=%s", schedule_id)


@router.post("/{schedule_id}/run-now", response_model=dict)
def run_now(schedule_id: int, db: Session = Depends(get_db)):
    """
    Ejecuta el ciclo inmediatamente sin esperar al próximo tick.
    Útil para probar el schedule o forzar una actualización.
    """
    config = db.get(ScheduleConfig, schedule_id)
    if not config:
        raise HTTPException(status_code=404, detail=f"No existe schedule con id {schedule_id}.")

    from app.agents.orchestrator import run_full_cycle
    try:
        result = run_full_cycle(config.url, db)
        config.last_run_at = __import__('datetime').datetime.now()
        config.last_run_status = "success"
        config.last_run_error = None
        db.commit()
        return {
            "message": "Ciclo ejecutado exitosamente.",
            "analysis_id": result.analysis_id,
            "proposals_count": result.proposals_count,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error en ejecución: {exc}")
