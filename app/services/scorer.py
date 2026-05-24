"""
Calcula SEO Score y GEO Score a partir de ScrapeData.
Heurísticas deterministas para demo de hackathon — no son auditorías reales.
"""
import logging

from app.services.scraper import ScrapeData

logger = logging.getLogger(__name__)

FAQ_TEXT_MARKERS = (
    "preguntas frecuentes",
    "preguntas más frecuentes",
    "preguntas mas frecuentes",
    "faq",
)


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _score_title_length(title: str, full: int = 20, partial: int = 10) -> int:
    length = len(title.strip())
    if 30 <= length <= 65:
        return full
    if length > 0:
        return partial
    return 0


def _score_meta_length(meta: str, full: int = 20, partial: int = 10) -> int:
    length = len(meta.strip())
    if 70 <= length <= 160:
        return full
    if length > 0:
        return partial
    return 0


def _count_questions(body_text: str) -> int:
    return body_text.count("?")


def _has_faq_text_section(body_text: str) -> bool:
    lowered = body_text.lower()
    return any(marker in lowered for marker in FAQ_TEXT_MARKERS)


def calculate_geo_score(scrape_data: ScrapeData) -> int:
    """
    GEO Score 0-100. Cinco criterios de 20 puntos (sección 10 del prompt v2).

    1. FAQ Schema / sección textual
    2. Metadatos (title + meta description)
    3. Contenido conversacional (densidad de preguntas)
    4. Estructura semántica (H1 + H2)
    5. Profundidad (word count)
    """
    score = 0

    # 1. FAQ (20 pts)
    if scrape_data.has_faq_schema:
        score += 20
    elif _has_faq_text_section(scrape_data.body_text):
        score += 10

    # 2. Metadatos (20 pts)
    score += _score_title_length(scrape_data.title, full=10, partial=5)
    score += _score_meta_length(scrape_data.meta_description, full=10, partial=5)

    # 3. Contenido conversacional (20 pts)
    questions = _count_questions(scrape_data.body_text)
    if questions >= 5:
        score += 20
    elif questions >= 2:
        score += 10

    # 4. Estructura semántica (20 pts)
    # El scraper guarda el primer H1; asumimos 1 H1 si existe texto.
    if scrape_data.h1.strip():
        score += 10
    if len(scrape_data.h2_list) >= 3:
        score += 10

    # 5. Profundidad (20 pts)
    if scrape_data.word_count >= 800:
        score += 20
    elif scrape_data.word_count >= 400:
        score += 10

    final = _clamp_score(score)
    logger.info("GEO Score calculado: %s para %s", final, scrape_data.url)
    return final


def calculate_seo_score(scrape_data: ScrapeData) -> int:
    """
    SEO Score 0-100. Cinco criterios de 20 puntos (RF-02).

    1. Title optimizado
    2. Meta description optimizada
    3. Jerarquía H1/H2
    4. Accesibilidad de imágenes (alt text)
    5. Longitud de contenido + links internos
    """
    score = 0

    # 1. Title (20 pts)
    score += _score_title_length(scrape_data.title)

    # 2. Meta description (20 pts)
    score += _score_meta_length(scrape_data.meta_description)

    # 3. Headings (20 pts)
    if scrape_data.h1.strip():
        score += 10
    if len(scrape_data.h2_list) >= 2:
        score += 10
    elif len(scrape_data.h2_list) == 1:
        score += 5

    # 4. Imágenes con alt (20 pts)
    if scrape_data.images_without_alt == 0:
        score += 20
    elif scrape_data.images_without_alt <= 3:
        score += 10

    # 5. Contenido y enlazado interno (20 pts)
    if scrape_data.word_count >= 500:
        score += 10
    elif scrape_data.word_count >= 200:
        score += 5

    if scrape_data.internal_links_count >= 5:
        score += 10
    elif scrape_data.internal_links_count >= 2:
        score += 5

    final = _clamp_score(score)
    logger.info("SEO Score calculado: %s para %s", final, scrape_data.url)
    return final
