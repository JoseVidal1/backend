from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    GEMINI_API_KEY: str
    DATABASE_URL: str = "sqlite:///./geo_copilot.db"
    CORS_ORIGINS: str = "http://localhost:3000"

    # WordPress REST (opcional — sin esto se usa mock al aprobar)
    WORDPRESS_URL: str | None = None
    WORDPRESS_USERNAME: str | None = None
    WORDPRESS_APP_PASSWORD: str | None = None
    WORDPRESS_POST_STATUS: str = "draft"  # draft | publish
    WORDPRESS_META_POST_ID: int | None = None  # post donde actualizar meta/excerpt
    WORDPRESS_DEFAULT_MEDIA_ID: int | None = None  # imagen para ALT_TEXT_FIX

    def get_cors_origins(self) -> list[str]:
        # Permite definir múltiples orígenes separados por coma en .env
        # Ej: CORS_ORIGINS=http://localhost:3000,https://mifrontend.com
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# Instancia singleton — todos los módulos importan esto:
# from app.config import settings
settings = Settings()
