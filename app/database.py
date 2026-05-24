import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# create_engine: crea la conexión a la base de datos.
# connect_args={"check_same_thread": False} es requerido solo para SQLite
# porque por defecto SQLite no permite que un mismo objeto de conexión
# se use desde múltiples threads, pero FastAPI puede hacer eso.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
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
    """Agrega columnas nuevas en SQLite sin perder datos (hackathon-friendly)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "scrape_results" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("scrape_results")}
    if "scrape_warning" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE scrape_results ADD COLUMN scrape_warning TEXT"))
        logger = logging.getLogger(__name__)
        logger.info("Migración SQLite: columna scrape_warning agregada a scrape_results.")


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
