"""
Script para resetear la base de datos desde cero y sembrar datos mock de GSC.
Uso: python init_db.py

ADVERTENCIA: elimina todas las tablas y las vuelve a crear.
"""
from app.database import Base, SessionLocal, engine
from app.models.gsc_opportunity import GSCOpportunity
from app.services.gsc_mock import GSC_MOCK_OPPORTUNITIES
import app.models  # noqa: F401 — registra todos los modelos en Base.metadata


def seed_gsc_opportunities(db) -> int:
    """Inserta oportunidades GSC mock. Retorna cuántas filas se crearon."""
    for row in GSC_MOCK_OPPORTUNITIES:
        db.add(GSCOpportunity(**row))
    db.commit()
    return len(GSC_MOCK_OPPORTUNITIES)


def main() -> None:
    print("Reseteando base de datos...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas.")

    db = SessionLocal()
    try:
        count = seed_gsc_opportunities(db)
        print(f"Seed GSC: {count} oportunidades insertadas en gsc_opportunities.")
    finally:
        db.close()

    print("Base de datos lista.")


if __name__ == "__main__":
    main()
