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

# Penalización máxima cuando se detecta bot-wall (los datos no son del sitio real)
_BOT_WALL_CAP = 20


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))


def _score_title_length(title: str, full: int = 20, partial: int = 10) -> int:
    """
    Rango óptimo SEO: 20-70 chars (antes era 30-65, muy estrecho para bancos).
    Parcial: cualquier título no vacío.
    """
    length = len(title.strip())
    if 20 <= length <= 70:
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


def _score_images(total_images: int, images_without_alt: int, full: int = 20, partial: int = 10) -> int:
    """
    Puntuación de accesibilidad de imágenes:
    - Sin imágenes en la página → 0 pts (no aplica; no se penaliza pero tampoco se premia)
    - Todas las imágenes tienen alt → full pts
    - ≤ 3 sin alt → partial pts
    - Más de 3 sin alt → 0 pts
    """
    if total_images == 0:
        return 0
    if images_without_alt == 0:
        return full
    if images_without_alt <= 3:
        return partial
    return 0


def calculate_seo_score(scrape_data: ScrapeData) -> int:
    """
    SEO Score 0-100. Cinco criterios de 20 puntos (RF-02).

    1. Title optimizado        (20 pts)
    2. Meta description        (20 pts)
    3. Jerarquía H1/H2         (20 pts)
    4. Alt text en imágenes    (20 pts) — 0 si no hay imágenes en la página
    5. Contenido + links       (20 pts)

    Si se detecta bot-wall (scrape_warning), el score se limita a {_BOT_WALL_CAP}
    porque los datos no representan el sitio real.
    """
    score = 0

    # 1. Title (20 pts)
    score += _score_title_length(scrape_data.title, full=20, partial=10)

    # 2. Meta description (20 pts)
    score += _score_meta_length(scrape_data.meta_description, full=20, partial=10)

    # 3. Headings (20 pts)
    if scrape_data.h1.strip():
        score += 10
    if len(scrape_data.h2_list) >= 2:
        score += 10
    elif len(scrape_data.h2_list) == 1:
        score += 5

    # 4. Alt text en imágenes (20 pts) — corregido: 0 pts si no hay imágenes
    score += _score_images(
        scrape_data.total_images,
        scrape_data.images_without_alt,
        full=20,
        partial=10,
    )

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

    # Bot-wall detectada: los datos no son del sitio real → limitamos el score
    if scrape_data.scrape_warning:
        final = min(final, _BOT_WALL_CAP)
        logger.warning(
            "SEO Score limitado a %s (bot-wall) para %s", final, scrape_data.url
        )
    else:
        logger.info("SEO Score calculado: %s para %s", final, scrape_data.url)

    return final


def calculate_geo_score(scrape_data: ScrapeData) -> int:
    """
    GEO Score 0-100. Cinco criterios de 20 puntos.

    1. FAQ Schema / sección textual     (20 pts)
    2. Metadatos (title + meta)         (20 pts)
    3. Contenido conversacional         (20 pts)
    4. Estructura semántica (H1 + H2)   (20 pts)
    5. Profundidad (word count)         (20 pts)

    Si se detecta bot-wall, el score se limita a {_BOT_WALL_CAP}.
    """
    score = 0

    # 1. FAQ (20 pts)
    if scrape_data.has_faq_schema:
        score += 20
    elif _has_faq_text_section(scrape_data.body_text):
        score += 10

    # 2. Metadatos (20 pts) — combinación de título y meta
    score += _score_title_length(scrape_data.title, full=10, partial=5)
    score += _score_meta_length(scrape_data.meta_description, full=10, partial=5)

    # 3. Contenido conversacional (20 pts)
    questions = _count_questions(scrape_data.body_text)
    if questions >= 5:
        score += 20
    elif questions >= 2:
        score += 10

    # 4. Estructura semántica (20 pts)
    if scrape_data.h1.strip():
        score += 10
    if len(scrape_data.h2_list) >= 3:
        score += 10
    elif len(scrape_data.h2_list) >= 1:
        score += 5

    # 5. Profundidad (20 pts)
    if scrape_data.word_count >= 800:
        score += 20
    elif scrape_data.word_count >= 400:
        score += 10
    elif scrape_data.word_count >= 150:
        score += 5

    final = _clamp_score(score)

    # Bot-wall detectada
    if scrape_data.scrape_warning:
        final = min(final, _BOT_WALL_CAP)
        logger.warning(
            "GEO Score limitado a %s (bot-wall) para %s", final, scrape_data.url
        )
    else:
        logger.info("GEO Score calculado: %s para %s", final, scrape_data.url)

    return final
