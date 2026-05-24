"""Oportunidades mockeadas de Google Search Console."""

GSC_MOCK_OPPORTUNITIES: list[dict] = [
    {
        "query": "tarjeta de crédito sin cuota de manejo colombia",
        "impressions": 12400,
        "position": 18.4,
        "ctr": 0.021,
    },
    {
        "query": "cómo sacar crédito de libranza",
        "impressions": 8700,
        "position": 24.1,
        "ctr": 0.015,
    },
    {
        "query": "mejor banco para abrir cuenta de ahorros",
        "impressions": 15300,
        "position": 31.7,
        "ctr": 0.012,
    },
    {
        "query": "crédito de consumo tasa de interés baja",
        "impressions": 6200,
        "position": 15.2,
        "ctr": 0.028,
    },
    {
        "query": "qué tarjeta me conviene en colombia",
        "impressions": 22100,
        "position": 42.3,
        "ctr": 0.008,
    },
    {
        "query": "cdt tasa fija hoy colombia",
        "impressions": 9800,
        "position": 12.6,
        "ctr": 0.034,
    },
    {
        "query": "cómo mejorar historial crediticio",
        "impressions": 7400,
        "position": 27.9,
        "ctr": 0.019,
    },
    {
        "query": "préstamo personal en línea aprobación rápida",
        "impressions": 11200,
        "position": 19.8,
        "ctr": 0.023,
    },
    {
        "query": "tarjeta de crédito para reportados en datacrédito",
        "impressions": 5600,
        "position": 35.5,
        "ctr": 0.011,
    },
    {
        "query": "comparar tarjetas de crédito colombia 2025",
        "impressions": 8900,
        "position": 22.0,
        "ctr": 0.017,
    },
]


def get_mock_opportunities() -> list[dict]:
    """Retorna copia de oportunidades GSC simuladas."""
    return [row.copy() for row in GSC_MOCK_OPPORTUNITIES]
