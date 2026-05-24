"""
Scheduler de monitoreo automático con APScheduler.
Corre dentro del mismo proceso de FastAPI — sin Redis, sin workers externos.
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Instancia global del scheduler — se inicia al arrancar FastAPI
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="America/Bogota")
    return _scheduler


def start_scheduler() -> None:
    """Arranca el scheduler. Llamar una vez al iniciar FastAPI."""
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler iniciado (timezone: America/Bogota).")


def stop_scheduler() -> None:
    """Detiene el scheduler limpiamente. Llamar al apagar FastAPI."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido.")


# ---------------------------------------------------------------------------
# Job que se ejecuta en cada tick del schedule
# ---------------------------------------------------------------------------

def _run_cycle_job(schedule_id: int, url: str) -> None:
    """
    Job que APScheduler llama automáticamente.
    Abre su propia sesión de DB porque corre en un thread separado.
    """
    from app.agents.orchestrator import run_full_cycle
    from app.database import SessionLocal
    from app.models.schedule_config import ScheduleConfig

    logger.info("[Scheduler] Ejecutando ciclo para schedule_id=%s url=%s", schedule_id, url)
    db = SessionLocal()
    try:
        run_full_cycle(url, db)

        # Actualizar estado en DB
        config = db.get(ScheduleConfig, schedule_id)
        if config:
            config.last_run_at = datetime.now()
            config.last_run_status = "success"
            config.last_run_error = None
            db.commit()

        logger.info("[Scheduler] Ciclo completado para schedule_id=%s", schedule_id)

    except Exception as exc:
        logger.error("[Scheduler] Ciclo falló schedule_id=%s: %s", schedule_id, exc)
        try:
            config = db.get(ScheduleConfig, schedule_id)
            if config:
                config.last_run_at = datetime.now()
                config.last_run_status = "error"
                config.last_run_error = str(exc)[:500]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Gestión de jobs
# ---------------------------------------------------------------------------

def _job_id(schedule_id: int) -> str:
    return f"geo_cycle_{schedule_id}"


def add_job(schedule_id: int, url: str, interval_minutes: int) -> datetime:
    """
    Registra un job en APScheduler.
    Retorna la próxima fecha de ejecución.
    """
    scheduler = get_scheduler()
    job_id = _job_id(schedule_id)

    # Si ya existe, lo reemplazamos (puede venir de un update)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    job = scheduler.add_job(
        func=_run_cycle_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=job_id,
        args=[schedule_id, url],
        replace_existing=True,
        misfire_grace_time=3600,  # si el server estuvo caído, ejecutar hasta 1h tarde
    )

    next_run = job.next_run_time
    logger.info(
        "[Scheduler] Job registrado: schedule_id=%s cada %smin próxima=%s",
        schedule_id,
        interval_minutes,
        next_run,
    )
    return next_run


def remove_job(schedule_id: int) -> None:
    """Elimina un job del scheduler."""
    scheduler = get_scheduler()
    job_id = _job_id(schedule_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("[Scheduler] Job eliminado: schedule_id=%s", schedule_id)


def pause_job(schedule_id: int) -> None:
    scheduler = get_scheduler()
    job_id = _job_id(schedule_id)
    if scheduler.get_job(job_id):
        scheduler.pause_job(job_id)
        logger.info("[Scheduler] Job pausado: schedule_id=%s", schedule_id)


def resume_job(schedule_id: int, url: str, interval_minutes: int) -> datetime:
    """Reactiva un job pausado. Retorna la próxima ejecución."""
    return add_job(schedule_id, url, interval_minutes)


def get_next_run(schedule_id: int) -> datetime | None:
    """Retorna la próxima fecha de ejecución de un job."""
    scheduler = get_scheduler()
    job = scheduler.get_job(_job_id(schedule_id))
    return job.next_run_time if job else None


def restore_active_schedules(db) -> int:
    """
    Al reiniciar FastAPI, re-registra todos los schedules activos de la DB.
    Sin esto, los jobs se pierden al reiniciar el servidor.
    Retorna cuántos jobs se restauraron.
    """
    from app.models.schedule_config import ScheduleConfig

    configs = (
        db.query(ScheduleConfig)
        .filter(ScheduleConfig.is_active == True)  # noqa: E712
        .all()
    )

    count = 0
    for config in configs:
        try:
            next_run = add_job(config.id, config.url, config.interval_minutes)
            config.next_run_at = next_run
            count += 1
        except Exception as exc:
            logger.error("No se pudo restaurar schedule_id=%s: %s", config.id, exc)

    if count:
        db.commit()
        logger.info("[Scheduler] %s schedules restaurados desde DB.", count)

    return count
