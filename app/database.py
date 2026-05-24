import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# create_engine: crea la conexión a la base de datos.
# connect_args={"check_same_thread": False} es requerido solo para SQLite
# porque por defecto SQLite no permite que un mismo objeto de conexión
# se use desde múltiples threads, pero FastAPI puede hacer eso.
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

# sessionmaker: fábrica que genera sesiones de DB.
# autocommit=False → los cambios no se guardan solos, hay que llamar .commit()
# autoflush=False  → los objetos no se sincronizan solos con la DB antes de cada query
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Base: clase padre de todos los modelos SQLAlchemy.
# Cuando un modelo hereda de Base, SQLAlchemy sabe que es una tabla.
class Base(DeclarativeBase):
    pass


def run_sqlite_migrations() -> None:
    """Agrega/renombra columnas en SQLite sin perder datos (hackathon-friendly).
    No hace nada si la DB es PostgreSQL."""
    if not _is_sqlite:
        return

    from sqlalchemy import inspect, text

    logger = logging.getLogger(__name__)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # --- scrape_results: agregar scrape_warning ---
    if "scrape_results" in tables:
        columns = {col["name"] for col in inspector.get_columns("scrape_results")}
        if "scrape_warning" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE scrape_results ADD COLUMN scrape_warning TEXT"))
            logger.info("Migración SQLite: columna scrape_warning agregada a scrape_results.")

    # --- schedule_configs: interval_hours → interval_minutes ---
    if "schedule_configs" in tables:
        sc_cols = {col["name"] for col in inspector.get_columns("schedule_configs")}
        if "interval_hours" in sc_cols and "interval_minutes" not in sc_cols:
            with engine.begin() as conn:
                # Añadir nueva columna con valor convertido (horas × 60)
                conn.execute(text(
                    "ALTER TABLE schedule_configs ADD COLUMN interval_minutes INTEGER"
                ))
                conn.execute(text(
                    "UPDATE schedule_configs SET interval_minutes = interval_hours * 60"
                ))
            logger.info("Migración SQLite: interval_hours → interval_minutes en schedule_configs.")


def get_db():
    """
    Dependency de FastAPI. Abre una sesión de DB para el request
    y la cierra automáticamente cuando el request termina.

    Uso en un router:
        def mi_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db  # FastAPI inyecta esta sesión en el endpoint
    finally:
        db.close()  # se ejecuta siempre, aunque haya un error
