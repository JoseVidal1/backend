import re


def clean_gemini_output(text: str) -> str:
    """
    Quita envoltorios ```markdown / ```json que Gemini a veces agrega.
    """
    if not text:
        return ""

    cleaned = text.strip()

    fenced = re.match(
        r"^```(?:markdown|md|json|html)?\s*\n([\s\S]*?)\n```\s*$",
        cleaned,
        flags=re.IGNORECASE,
    )
    if fenced:
        return fenced.group(1).strip()

    cleaned = re.sub(r"^```(?:markdown|md|json|html)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()
