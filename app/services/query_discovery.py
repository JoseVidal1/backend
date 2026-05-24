"""
Query Discovery — descubre queries reales sin APIs pagas.
Fuentes: Google Suggest (endpoint público) + DuckDuckGo Autocomplete.
"""
import hashlib
import logging
from urllib.parse import quote

import requests

from app.services.scraper import ScrapeData

logger = logging.getLogger(__name__)

# Timeout corto: si Google/DDG no responden en 4s, los saltamos
_SUGGEST_TIMEOUT = 4

# Headers para que Google no rechace la petición
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "es-CO,es;q=0.9",
}


# ---------------------------------------------------------------------------
# Fuente 1: Google Suggest
# ---------------------------------------------------------------------------

def fetch_google_suggest(seed: str, max_results: int = 8) -> list[str]:
    """
    Llama al endpoint público de sugerencias de Google (no requiere API key).
    Retorna hasta max_results sugerencias para el seed dado.
    """
    url = (
        "https://suggestqueries.google.com/complete/search"
        f"?q={quote(seed)}&hl=es&gl=co&client=firefox"
    )
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_SUGGEST_TIMEOUT)
        resp.raise_for_status()
        # Firefox client devuelve [query, [sugerencia1, sugerencia2, ...]]
        data = resp.json()
        suggestions = data[1] if isinstance(data, list) and len(data) > 1 else []
        return [str(s).strip() for s in suggestions[:max_results] if s]
    except Exception as exc:
        logger.warning("Google Suggest falló para '%s': %s", seed, exc)
        return []


# ---------------------------------------------------------------------------
# Fuente 2: DuckDuckGo Autocomplete
# ---------------------------------------------------------------------------

def fetch_duckduckgo_suggest(seed: str, max_results: int = 5) -> list[str]:
    """
    Llama al endpoint de autocomplete de DuckDuckGo (no requiere API key).
    Retorna hasta max_results sugerencias.
    """
    url = f"https://duckduckgo.com/ac/?q={quote(seed)}&type=list&kl=co-es"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_SUGGEST_TIMEOUT)
        resp.raise_for_status()
        # Devuelve [query, [sugerencia1, sugerencia2, ...]]
        data = resp.json()
        suggestions = data[1] if isinstance(data, list) and len(data) > 1 else []
        return [str(s).strip() for s in suggestions[:max_results] if s]
    except Exception as exc:
        logger.warning("DuckDuckGo Suggest falló para '%s': %s", seed, exc)
        return []


# ---------------------------------------------------------------------------
# Extraer seeds del contenido scrapeado
# ---------------------------------------------------------------------------

def extract_seeds(scrape_data: ScrapeData) -> list[str]:
    """
    Genera 3-5 seeds de búsqueda a partir del contenido real de la página.
    Combina: título, H1, primeros H2s y el dominio del sitio.
    """
    seeds: list[str] = []

    # El título suele ser la marca o el tema principal
    if scrape_data.title and len(scrape_data.title.strip()) > 3:
        seeds.append(scrape_data.title.strip()[:60])

    # El H1 describe el tema central de la página
    if scrape_data.h1 and len(scrape_data.h1.strip()) > 5:
        h1_clean = scrape_data.h1.strip()[:80]
        if h1_clean not in seeds:
            seeds.append(h1_clean)

    # Los primeros 2 H2s como seeds adicionales
    for h2 in scrape_data.h2_list[:2]:
        h2_clean = h2.strip()[:80]
        if len(h2_clean) > 5 and h2_clean not in seeds:
            seeds.append(h2_clean)

    # Si no hay suficientes seeds, agregamos el dominio como fallback
    if len(seeds) < 2:
        from urllib.parse import urlparse
        domain = urlparse(scrape_data.url).netloc.replace("www.", "")
        if domain:
            seeds.append(domain)

    logger.info("Seeds extraídos de '%s': %s", scrape_data.url, seeds)
    return seeds[:5]  # máximo 5 seeds para no saturar las APIs


# ---------------------------------------------------------------------------
# Generar posición/impresiones/CTR mock realistas
# ---------------------------------------------------------------------------

def _mock_metrics(query: str) -> dict:
    """
    Genera métricas mock deterministas (reproducibles para el mismo query).
    Simula datos del rango "oportunidad": posición 10-45, impresiones medias.
    """
    # Hash del query para que siempre dé los mismos valores
    h = int(hashlib.md5(query.encode()).hexdigest(), 16)

    impressions = 3000 + (h % 18000)       # entre 3k y 21k
    position = 10.0 + (h % 36) + (h % 10) * 0.1   # entre 10.0 y 46.0
    # CTR decrece con la posición: top 10 ~4-8%, posición 30+ ~0.5-1.5%
    ctr = round(max(0.005, 0.08 - position * 0.0018), 3)

    return {
        "impressions": impressions,
        "position": round(position, 1),
        "ctr": ctr,
    }


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def discover_queries(seeds: list[str], max_per_seed: int = 5) -> list[dict]:
    """
    Descubre queries reales combinando Google Suggest y DuckDuckGo.
    Retorna lista de dicts listos para insertar en gsc_opportunities:
        {"query": str, "impressions": int, "position": float, "ctr": float}

    Si ambas fuentes fallan (sin internet), retorna lista vacía.
    """
    if not seeds:
        return []

    all_queries: set[str] = set()

    for seed in seeds:
        google = fetch_google_suggest(seed, max_results=max_per_seed)
        ddg = fetch_duckduckgo_suggest(seed, max_results=max_per_seed)

        for q in google + ddg:
            q_clean = q.strip().lower()
            if len(q_clean) > 8:  # filtramos sugerencias demasiado cortas
                all_queries.add(q_clean)

    if not all_queries:
        logger.warning("Query discovery no encontró resultados. ¿Sin acceso a internet?")
        return []

    results = []
    for query in sorted(all_queries):  # orden determinista
        metrics = _mock_metrics(query)
        results.append({"query": query, **metrics})

    # Ordenar por impresiones descendente (las mejores oportunidades primero)
    results.sort(key=lambda x: x["impressions"], reverse=True)

    logger.info(
        "Query discovery completado: %s seeds → %s queries únicos",
        len(seeds),
        len(results),
    )
    return results[:20]  # máximo 20 oportunidades por análisis
