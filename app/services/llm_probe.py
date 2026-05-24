import json
import logging
import unicodedata
from dataclasses import dataclass, field

from app.prompts.templates import prompt_llm_probe_judge
from app.services.gemini_client import GeminiClient, get_gemini_client

logger = logging.getLogger(__name__)

RESPONSE_EXCERPT_MAX = 500

# Queries financieras del reto — simulan lo que un colombiano le pregunta a un LLM.
DEFAULT_PROBE_QUERIES: list[str] = [
    "¿qué tarjeta de crédito me conviene en Colombia?",
    "¿cuál es el mejor banco para abrir una cuenta de ahorros?",
    "¿cómo sacar un crédito de libranza en Colombia?",
    "¿qué CDT tiene mejor tasa hoy en Colombia?",
    "¿cómo mejorar mi historial crediticio en Datacrédito?",
    "¿qué banco tiene tarjeta de crédito sin cuota de manejo?",
    "¿dónde pedir un préstamo personal con aprobación rápida en Colombia?",
]

COMPETITOR_KEYWORDS: dict[str, str] = {
    "bancolombia": "Bancolombia",
    "davivienda": "Davivienda",
    "bbva": "BBVA",
    "banco de bogota": "Banco de Bogotá",
    "banco de bogotá": "Banco de Bogotá",
    "banco popular": "Banco Popular",
    "popular": "Banco Popular",
    "av villas": "AV Villas",
    "avvillas": "AV Villas",
    "scotiabank": "Scotiabank Colpatria",
    "colpatria": "Scotiabank Colpatria",
    "banco caja social": "Banco Caja Social",
    "caja social": "Banco Caja Social",
}


@dataclass
class ProbeData:
    query: str
    llm_response_excerpt: str
    serfinanza_mentioned: bool
    competitors_mentioned: list[str] = field(default_factory=list)
    similarity_score: float = 0.0
    needs_content: bool = True


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    normalized = unicodedata.normalize("NFD", lowered)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _detect_serfinanza_mention(response: str) -> bool:
    normalized = _normalize_text(response)
    return "serfinanza" in normalized


def _detect_competitors(response: str) -> list[str]:
    normalized = _normalize_text(response)
    found: list[str] = []
    seen: set[str] = set()

    for keyword, label in COMPETITOR_KEYWORDS.items():
        if keyword in normalized and label not in seen:
            seen.add(label)
            found.append(label)

    return found


def _merge_judge_result(
    heuristic_serfinanza: bool,
    heuristic_competitors: list[str],
    judge: dict,
) -> tuple[bool, list[str], float]:
    serfinanza = bool(judge.get("serfinanza_mentioned", heuristic_serfinanza))
    if not serfinanza:
        serfinanza = heuristic_serfinanza

    competitors_raw = judge.get("competitors_mentioned", [])
    competitors: list[str] = []
    if isinstance(competitors_raw, list):
        competitors = [str(c) for c in competitors_raw if str(c).strip()]

    merged = list(dict.fromkeys(heuristic_competitors + competitors))

    try:
        similarity = float(judge.get("similarity_score", 0.0))
    except (TypeError, ValueError):
        similarity = 0.0
    similarity = max(0.0, min(1.0, similarity))

    return serfinanza, merged, similarity


def probe(query: str, client: GeminiClient | None = None) -> ProbeData:
    """
    Ejecuta LLM probing para una query:
    1. Pregunta directa a Gemini
    2. Heurística local de mención y competidores
    3. Gemini-as-judge para similarity_score
    """
    gemini = client or get_gemini_client()
    logger.info("LLM probe: %s", query)

    llm_response = gemini.generate(query)
    excerpt = llm_response[:RESPONSE_EXCERPT_MAX]

    heuristic_serfinanza = _detect_serfinanza_mention(llm_response)
    heuristic_competitors = _detect_competitors(llm_response)

    judge = gemini.generate_json(prompt_llm_probe_judge(llm_response))
    serfinanza_mentioned, competitors, similarity_score = _merge_judge_result(
        heuristic_serfinanza,
        heuristic_competitors,
        judge,
    )

    return ProbeData(
        query=query,
        llm_response_excerpt=excerpt,
        serfinanza_mentioned=serfinanza_mentioned,
        competitors_mentioned=competitors,
        similarity_score=similarity_score,
        needs_content=not serfinanza_mentioned,
    )


def run_full_probe(
    queries: list[str] | None = None,
    client: GeminiClient | None = None,
) -> list[ProbeData]:
    """Itera todas las queries (por defecto las 7 del reto)."""
    selected = queries or DEFAULT_PROBE_QUERIES
    return [probe(q, client=client) for q in selected]


def probe_data_to_db_fields(data: ProbeData) -> dict:
    """Convierte ProbeData a campos para el modelo SQLAlchemy."""
    return {
        "query": data.query,
        "llm_response_excerpt": data.llm_response_excerpt,
        "serfinanza_mentioned": data.serfinanza_mentioned,
        "competitors_mentioned_json": json.dumps(data.competitors_mentioned, ensure_ascii=False),
        "similarity_score": data.similarity_score,
        "needs_content": data.needs_content,
    }
