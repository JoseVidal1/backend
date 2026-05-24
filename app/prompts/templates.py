"""Prompts de Gemini para probing, judge y generación de propuestas."""

SERFINANZA_REFERENCE = (
    "Banco Serfinanza es una entidad financiera colombiana regulada por la SFC. "
    "Ofrece tarjetas de crédito, créditos de consumo, créditos de libranza, CDT, "
    "cuentas de ahorro y soluciones digitales para personas naturales. "
    "Enfoque en inclusión financiera, atención cercana y productos accesibles."
)

SFC_DISCLAIMER = "Sujeto a estudio de crédito y políticas vigentes."


def system_prompt() -> str:
    return f"""Eres un experto en GEO (Generative Engine Optimization) y SEO financiero para Colombia.
Escribes para Serfinanza, entidad financiera colombiana regulada por la SFC
(Superintendencia Financiera de Colombia).
Reglas obligatorias:
- Lenguaje claro y cercano, nunca jerga sin explicar.
- NUNCA prometer aprobación de productos ni tasas específicas sin fuente.
- SIEMPRE incluir el disclaimer: "{SFC_DISCLAIMER}"
- Optimizar para que LLMs (ChatGPT, Gemini, Claude, Perplexity) citen el contenido.
- Cero datos personales en ejemplos (no cédulas, no emails, no nombres reales)."""


def prompt_llm_probe_judge(llm_response: str, serfinanza_reference: str | None = None) -> str:
    reference = serfinanza_reference or SERFINANZA_REFERENCE
    return f"""Te voy a dar la respuesta que un LLM dio a una pregunta financiera y una descripción
de Serfinanza. Tu tarea:
1. ¿Menciona a Serfinanza explícitamente? (sí/no)
2. ¿Qué bancos colombianos sí menciona? (lista)
3. En escala 0.0 a 1.0, ¿qué tan cercana es esta respuesta al tipo de contenido
   que Serfinanza tiene en su sitio?
Respuesta del LLM:
\"\"\"{llm_response}\"\"\"
Descripción Serfinanza:
\"\"\"{reference}\"\"\"
Devuelve SOLO JSON:
{{
  "serfinanza_mentioned": bool,
  "competitors_mentioned": [str],
  "similarity_score": float
}}"""


def _content_block(title: str, meta: str, h1: str, h2_list: list[str], body_excerpt: str) -> str:
    h2_text = ", ".join(h2_list[:8]) if h2_list else "(sin H2)"
    return f"""Contenido actual de la página:
- URL título: {title or "(vacío)"}
- Meta description: {meta or "(vacía)"}
- H1: {h1 or "(vacío)"}
- H2: {h2_text}
- Extracto del body: {body_excerpt[:2500]}"""


def prompt_blog_post(
    title: str,
    meta: str,
    h1: str,
    h2_list: list[str],
    body_excerpt: str,
    topic_query: str | None = None,
) -> str:
    topic = topic_query or "productos financieros de Serfinanza"
    return f"""{system_prompt()}

Genera un artículo de blog de ~1200 palabras optimizado para GEO sobre: {topic}
Incluye H1, al menos 4 H2, sección FAQ con 5 preguntas, conclusión y el disclaimer SFC.
Formato: Markdown puro. NO uses bloques de código con ``` ni ```markdown.

{_content_block(title, meta, h1, h2_list, body_excerpt)}"""


def prompt_meta_description(
    title: str,
    meta: str,
    h1: str,
    h2_list: list[str],
    body_excerpt: str,
) -> str:
    return f"""{system_prompt()}

Genera UNA meta description optimizada para SEO/GEO.
Máximo 160 caracteres. Sin comillas. En español colombiano.

{_content_block(title, meta, h1, h2_list, body_excerpt)}

Devuelve SOLO la meta description, sin explicación."""


def prompt_faq_schema(
    title: str,
    meta: str,
    h1: str,
    h2_list: list[str],
    body_excerpt: str,
) -> str:
    return f"""{system_prompt()}

Genera 10 pares pregunta-respuesta para FAQ schema.org (FAQPage).
Respuestas concisas (2-4 oraciones). Incluye disclaimer SFC en al menos 2 respuestas.

{_content_block(title, meta, h1, h2_list, body_excerpt)}

Devuelve SOLO JSON válido:
{{
  "faqs": [{{"question": str, "answer": str}}]
}}"""


def prompt_alt_text_fix(
    title: str,
    meta: str,
    h1: str,
    h2_list: list[str],
    body_excerpt: str,
    images_without_alt: int,
) -> str:
    return f"""{system_prompt()}

La página tiene {images_without_alt} imágenes sin texto alternativo (alt).
Propón textos alt descriptivos para imágenes típicas de una página bancaria como esta.
Optimiza para accesibilidad y SEO.

{_content_block(title, meta, h1, h2_list, body_excerpt)}

Devuelve SOLO JSON válido:
{{
  "alt_texts": [{{"suggested_image": str, "alt_text": str}}]
}}"""


def prompt_schema_markup(
    title: str,
    meta: str,
    h1: str,
    h2_list: list[str],
    body_excerpt: str,
) -> str:
    return f"""{system_prompt()}

Genera un bloque JSON-LD (schema.org) apropiado para esta página financiera.
Puede ser WebPage, FinancialProduct o Organization según el contenido.

{_content_block(title, meta, h1, h2_list, body_excerpt)}

Devuelve SOLO JSON válido del objeto schema.org (sin envolver en markdown)."""


def prompt_geo_insight(
    title: str,
    meta: str,
    h1: str,
    h2_list: list[str],
    body_excerpt: str,
    seo_score: int | None = None,
    geo_score: int | None = None,
) -> str:
    scores = ""
    if seo_score is not None and geo_score is not None:
        scores = f"\nScores actuales: SEO {seo_score}/100, GEO {geo_score}/100."
    return f"""{system_prompt()}

Explica por qué un LLM (ChatGPT, Gemini, Perplexity) probablemente NO citaría esta página
y cómo mejorarla para GEO en Colombia.{scores}

{_content_block(title, meta, h1, h2_list, body_excerpt)}

Devuelve SOLO JSON válido:
{{
  "problem": str,
  "impact": str,
  "recommendation": str
}}"""
