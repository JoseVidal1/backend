import json
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# User-agent real para evitar que sitios bloqueen el scraper por ser un bot obvio
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

MAX_BODY_CHARS = 10_000  # truncamos el body para no saturar la DB ni los prompts

# Señales de páginas anti-bot (Radware, Cloudflare, FingerprintJS, etc.)
BOT_WALL_TITLE_MARKERS = ("radware page", "just a moment", "attention required", "access denied")
BOT_WALL_META_MARKERS = ("loader page",)
BOT_WALL_BODY_MARKERS = (
    "verifying your browser",
    "checking your browser",
    "please wait while we verify",
    "fingerprintjs",
    "cf-browser-verification",
    "radware",
    "incident id",
)

SCRAPE_WARNING_BOT = (
    "Protección anti-bots detectada (Radware/Cloudflare/JS). "
    "Los scores SEO/GEO se calcularon sobre la página de verificación, no sobre el sitio real. "
    "Integración Playwright planificada para fase 2."
)


def _is_bot_protection_page(title: str, meta: str, body_text: str, raw_html: str) -> bool:
    """Detecta si la respuesta es una pantalla de verificación, no el sitio real."""
    title_l = title.lower()
    meta_l = meta.lower()
    body_l = body_text.lower()
    html_l = raw_html.lower()

    if any(m in title_l for m in BOT_WALL_TITLE_MARKERS):
        return True
    if meta_l and any(m in meta_l for m in BOT_WALL_META_MARKERS):
        return True
    if body_l and sum(1 for m in BOT_WALL_BODY_MARKERS if m in body_l or m in html_l) >= 2:
        return True
    if "fingerprintjs" in html_l and len(body_text.split()) < 50:
        return True
    return False


def detect_scrape_warning(
    title: str | None,
    meta: str | None,
    body_text: str | None,
) -> str | None:
    """Retorna mensaje de advertencia si los datos parecen una pantalla anti-bot."""
    if _is_bot_protection_page(
        title or "",
        meta or "",
        body_text or "",
        body_text or "",
    ):
        return SCRAPE_WARNING_BOT
    return None


@dataclass
class ScrapeData:
    url: str
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    h2_list: list[str] = field(default_factory=list)
    body_text: str = ""
    has_faq_schema: bool = False
    has_structured_data: bool = False
    word_count: int = 0
    internal_links_count: int = 0
    images_without_alt: int = 0
    scrape_warning: str | None = None

    def h2_list_as_json(self) -> str:
        """Serializa h2_list a string JSON para guardar en la DB."""
        return json.dumps(self.h2_list, ensure_ascii=False)


def _iter_schema_nodes(data) -> list[dict]:
    """Aplana objetos schema.org anidados (@graph, listas, etc.)."""
    nodes: list[dict] = []

    if isinstance(data, list):
        for item in data:
            nodes.extend(_iter_schema_nodes(item))
        return nodes

    if not isinstance(data, dict):
        return nodes

    nodes.append(data)

    graph = data.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            nodes.extend(_iter_schema_nodes(item))

    return nodes


def _schema_type_matches(node: dict, schema_type: str) -> bool:
    """Compara @type aceptando string o lista (ej. ['WebPage', 'FAQPage'])."""
    node_type = node.get("@type")
    if isinstance(node_type, list):
        return schema_type in node_type
    return node_type == schema_type


def _extract_structured_data(soup: BeautifulSoup) -> tuple[bool, bool]:
    """
    Lee scripts application/ld+json del HTML.
    Retorna (has_structured_data, has_faq_schema).
    """
    has_structured_data = False
    has_faq_schema = False

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        has_structured_data = True

        for node in _iter_schema_nodes(data):
            if _schema_type_matches(node, "FAQPage"):
                has_faq_schema = True
                break

        if has_faq_schema:
            break

    return has_structured_data, has_faq_schema


def scrape(url: str) -> ScrapeData:
    """
    Descarga y parsea una URL. Devuelve un ScrapeData con todo lo extraído.
    Lanza HTTPException si la URL no responde o devuelve un error HTTP.
    """
    logger.info(f"Scrapeando: {url}")

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="La URL tardó demasiado en responder (timeout 10s).")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail="No se pudo conectar a la URL. Verifica que esté activa.")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"La URL devolvió un error HTTP: {e}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Error al hacer el request: {e}")

    soup = BeautifulSoup(response.text, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    meta_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_tag.get("content", "").strip() if meta_tag else ""

    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(strip=True) if h1_tag else ""

    h2_list = [tag.get_text(strip=True) for tag in soup.find_all("h2")]

    # ld+json debe leerse ANTES de eliminar <script> del DOM
    has_structured_data, has_faq_schema = _extract_structured_data(soup)

    images = soup.find_all("img")
    images_without_alt = sum(1 for img in images if not img.get("alt", "").strip())

    domain = urlparse(url).netloc
    all_links = soup.find_all("a", href=True)
    internal_links_count = sum(
        1 for a in all_links
        if a["href"].startswith("/") or domain in a["href"]
    )

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    body_text = soup.get_text(separator=" ", strip=True)
    body_text = " ".join(body_text.split())
    body_text = body_text[:MAX_BODY_CHARS]
    word_count = len(body_text.split())

    scrape_warning = None
    if _is_bot_protection_page(title, meta_description, body_text, response.text):
        scrape_warning = SCRAPE_WARNING_BOT
        logger.warning("Bot protection detectada en %s (title=%s) — scrape_warning activo", url, title)

    logger.info(
        "Scraping completado: %s chars, %s palabras, H2s: %s, structured_data: %s, faq_schema: %s",
        len(body_text),
        word_count,
        len(h2_list),
        has_structured_data,
        has_faq_schema,
    )

    return ScrapeData(
        url=url,
        title=title,
        meta_description=meta_description,
        h1=h1,
        h2_list=h2_list,
        body_text=body_text,
        has_faq_schema=has_faq_schema,
        has_structured_data=has_structured_data,
        word_count=word_count,
        internal_links_count=internal_links_count,
        images_without_alt=images_without_alt,
        scrape_warning=scrape_warning,
    )
