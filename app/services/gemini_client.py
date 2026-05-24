import json
import logging
import re

import google.generativeai as genai
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"


def _map_gemini_error(exc: Exception) -> HTTPException:
    """Traduce errores de Gemini a HTTPException con mensaje útil en español."""
    message = str(exc).lower()

    if "429" in str(exc) or "quota" in message or "rate limit" in message or "resource_exhausted" in message:
        return HTTPException(
            status_code=429,
            detail=(
                "Cuota de Gemini agotada (free tier: ~20 solicitudes/día por modelo). "
                "Espera 1–2 minutos y reintenta, o crea otra API key en "
                "https://aistudio.google.com/app/apikey"
            ),
        )

    if "api key" in message or "api_key" in message or "permission denied" in message or "403" in str(exc):
        return HTTPException(
            status_code=401,
            detail=(
                "API key de Gemini inválida o sin permisos. "
                "Revisa GEMINI_API_KEY en .env y reinicia uvicorn por completo."
            ),
        )

    if "safety" in message or "respuesta vacía" in message:
        return HTTPException(
            status_code=503,
            detail="Gemini bloqueó la respuesta (filtro de seguridad). Intenta con otra query.",
        )

    return HTTPException(status_code=503, detail=f"Servicio de IA no disponible: {exc}")


class GeminiClient:
    """Cliente reutilizable para llamadas a Gemini."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name

    def generate(self, prompt: str) -> str:
        """Envía un prompt y retorna el texto de la respuesta."""
        try:
            response = self.model.generate_content(prompt)
            if not response.text:
                raise ValueError("Respuesta vacía (posible safety filter)")
            return response.text.strip()
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Gemini falló: %s", e)
            raise _map_gemini_error(e) from e

    def generate_json(self, prompt: str) -> dict:
        """Pide JSON estructurado y lo parsea."""
        text = self.generate(
            prompt + "\n\nDevuelve SOLO JSON válido, sin markdown, sin ```"
        )
        text = _clean_json_text(text)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("JSON inválido de Gemini: %s | texto: %s", e, text[:200])
            raise HTTPException(
                status_code=503,
                detail="La IA devolvió un formato inválido. Intenta de nuevo.",
            )


def _clean_json_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    """Singleton lazy — una instancia por proceso."""
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client


def reset_gemini_client() -> None:
    """Fuerza recarga del cliente (útil tras cambiar GEMINI_API_KEY en .env)."""
    global _client
    _client = None
