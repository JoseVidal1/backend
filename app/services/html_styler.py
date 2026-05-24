"""Estilos inline Serfinanza para contenido publicado en WordPress."""

from bs4 import BeautifulSoup

# Paleta corporativa bancaria Serfinanza
_TAG_STYLES: dict[str, str] = {
    "h1": (
        "font-family: 'Segoe UI', Georgia, serif; color: #003366; "
        "font-size: 28px; font-weight: 700; margin: 24px 0 16px; line-height: 1.3;"
    ),
    "h2": (
        "font-family: 'Segoe UI', Georgia, serif; color: #004080; "
        "font-size: 22px; font-weight: 600; margin: 20px 0 12px; "
        "border-bottom: 2px solid #0066cc; padding-bottom: 6px; line-height: 1.35;"
    ),
    "h3": (
        "font-family: 'Segoe UI', Georgia, serif; color: #005599; "
        "font-size: 18px; font-weight: 600; margin: 16px 0 8px; line-height: 1.4;"
    ),
    "p": (
        "font-family: 'Segoe UI', Arial, sans-serif; color: #333333; "
        "font-size: 16px; line-height: 1.7; margin: 0 0 14px;"
    ),
    "ul": (
        "font-family: 'Segoe UI', Arial, sans-serif; color: #333333; "
        "font-size: 16px; line-height: 1.7; margin: 0 0 16px 24px; padding: 0;"
    ),
    "ol": (
        "font-family: 'Segoe UI', Arial, sans-serif; color: #333333; "
        "font-size: 16px; line-height: 1.7; margin: 0 0 16px 24px; padding: 0;"
    ),
    "li": "margin-bottom: 6px; line-height: 1.6;",
    "strong": "color: #003366; font-weight: 700;",
    "em": "color: #555555; font-style: italic;",
    "blockquote": (
        "border-left: 4px solid #0066cc; margin: 16px 0; padding: 12px 20px; "
        "background-color: #f0f6fc; color: #004080; font-style: italic;"
    ),
    "a": "color: #0066cc; text-decoration: underline;",
    "hr": "border: none; border-top: 1px solid #cce0f5; margin: 24px 0;",
    "code": (
        "background-color: #f4f4f4; color: #003366; padding: 2px 6px; "
        "border-radius: 3px; font-size: 14px;"
    ),
}

_WRAPPER_STYLE = (
    "font-family: 'Segoe UI', Arial, sans-serif; color: #333333; "
    "max-width: 800px; line-height: 1.7;"
)

_DISCLAIMER_STYLE = (
    "font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; "
    "color: #666666; font-style: italic; margin-top: 24px; "
    "padding: 12px 16px; background-color: #f9f9f9; border-left: 3px solid #0066cc;"
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
