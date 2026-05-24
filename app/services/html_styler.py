"""
Estilos inline Serfinanza para contenido publicado en WordPress.

Paleta extraída directamente de bancoserfinanza.com (tema Astra):
  --ast-global-color-0 : #0170B9  → azul principal
  --ast-global-color-3 : #4B4F58  → texto cuerpo
  Font: 'Noto Sans', sans-serif
  H1: 40px / H2: 32px / H3: 26px
  Body: 18px / Container max-width: 1240px
"""

from bs4 import BeautifulSoup

# ── Tokens de marca ──────────────────────────────────────────────────────────
_BLUE     = "#0170B9"   # color corporativo principal
_BLUE_DK  = "#015a94"   # hover / bordes (10 % más oscuro)
_BLUE_LT  = "#e6f2fa"   # fondos suaves
_TEXT     = "#4B4F58"   # color de cuerpo (--ast-global-color-3)
_TEXT_LT  = "#6b7280"   # texto secundario
_FONT     = "'Noto Sans', sans-serif"

# ── Estilos por etiqueta ─────────────────────────────────────────────────────
_TAG_STYLES: dict[str, str] = {
    "h1": (
        f"font-family: {_FONT}; color: {_BLUE}; "
        "font-size: 40px; font-weight: 700; "
        "margin: 28px 0 16px; line-height: 1.2;"
    ),
    "h2": (
        f"font-family: {_FONT}; color: {_BLUE}; "
        "font-size: 32px; font-weight: 600; "
        f"margin: 24px 0 12px; border-bottom: 2px solid {_BLUE}; "
        "padding-bottom: 8px; line-height: 1.25;"
    ),
    "h3": (
        f"font-family: {_FONT}; color: {_BLUE_DK}; "
        "font-size: 26px; font-weight: 600; "
        "margin: 20px 0 10px; line-height: 1.3;"
    ),
    "h4": (
        f"font-family: {_FONT}; color: {_TEXT}; "
        "font-size: 20px; font-weight: 600; "
        "margin: 16px 0 8px; line-height: 1.35;"
    ),
    "p": (
        f"font-family: {_FONT}; color: {_TEXT}; "
        "font-size: 18px; line-height: 1.7; margin: 0 0 16px;"
    ),
    "ul": (
        f"font-family: {_FONT}; color: {_TEXT}; "
        "font-size: 18px; line-height: 1.7; "
        "margin: 0 0 18px 28px; padding: 0;"
    ),
    "ol": (
        f"font-family: {_FONT}; color: {_TEXT}; "
        "font-size: 18px; line-height: 1.7; "
        "margin: 0 0 18px 28px; padding: 0;"
    ),
    "li": f"color: {_TEXT}; margin-bottom: 8px; line-height: 1.65;",
    "strong": f"color: {_BLUE_DK}; font-weight: 700;",
    "em": f"color: {_TEXT_LT}; font-style: italic;",
    "blockquote": (
        f"border-left: 4px solid {_BLUE}; margin: 20px 0; "
        f"padding: 14px 24px; background-color: {_BLUE_LT}; "
        f"color: {_TEXT}; font-style: italic; font-size: 18px; "
        "border-radius: 0 4px 4px 0;"
    ),
    "a": f"color: {_BLUE}; text-decoration: underline;",
    "hr": f"border: none; border-top: 1px solid {_BLUE_LT}; margin: 28px 0;",
    "code": (
        f"background-color: {_BLUE_LT}; color: {_BLUE_DK}; "
        "padding: 2px 6px; border-radius: 3px; font-size: 15px;"
    ),
    "table": (
        f"width: 100%; border-collapse: collapse; "
        f"font-family: {_FONT}; font-size: 16px; margin: 16px 0 24px;"
    ),
    "th": (
        f"background-color: {_BLUE}; color: #ffffff; "
        "padding: 10px 14px; text-align: left; font-weight: 600;"
    ),
    "td": (
        f"border: 1px solid {_BLUE_LT}; padding: 10px 14px; "
        f"color: {_TEXT}; vertical-align: top;"
    ),
}

_WRAPPER_STYLE = (
    f"font-family: {_FONT}; color: {_TEXT}; "
    "max-width: 1240px; line-height: 1.7; "
    "background-color: #ffffff; padding: 0;"
)

_DISCLAIMER_STYLE = (
    f"font-family: {_FONT}; font-size: 14px; "
    f"color: {_TEXT_LT}; font-style: italic; margin-top: 28px; "
    f"padding: 14px 18px; background-color: {_BLUE_LT}; "
    f"border-left: 4px solid {_BLUE}; border-radius: 0 4px 4px 0;"
)


def apply_inline_styles(html: str, wrap: bool = True) -> str:
    """Aplica estilos inline a HTML antes de publicar en WordPress."""
    if not html or not html.strip():
        return html

    soup = BeautifulSoup(html, "lxml")

    # BeautifulSoup con lxml envuelve en html/body; trabajamos el body
    body = soup.body if soup.body else soup

    for tag_name, style in _TAG_STYLES.items():
        for tag in body.find_all(tag_name):
            existing = tag.get("style", "")
            tag["style"] = f"{existing}; {style}".strip("; ")

    inner = "".join(str(c) for c in body.children) if body.name == "body" else str(body)

    if wrap:
        return f'<div style="{_WRAPPER_STYLE}">{inner}</div>'

    return inner


def styled_disclaimer(text: str) -> str:
    return f'<p style="{_DISCLAIMER_STYLE}">{text}</p>'
