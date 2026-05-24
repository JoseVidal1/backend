# GEO Copilot — Backend (Serfinanza Hackathon)

Backend FastAPI para **GEO Copilot**: agente que audita, recomienda, edita y aprende para mejorar la visibilidad de Serfinanza en motores generativos (ChatGPT, Gemini, Perplexity, Claude).

**4 verbos del MVP:** AUDITAR → RECOMENDAR → EDITAR → APRENDER

---

## Levantar en 3 comandos

### Windows (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
# Edita .env → pon tu GEMINI_API_KEY real

uvicorn app.main:app --reload
```

### Linux / Mac

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env → pon tu GEMINI_API_KEY real

uvicorn app.main:app --reload
```

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### Resetear DB (opcional)

```powershell
python init_db.py
```

Borra todo y siembra 10 oportunidades GSC mock.

---

## Variables de entorno

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `GEMINI_API_KEY` | Sí | — | [API key Gemini](https://aistudio.google.com/app/apikey) |
| `DATABASE_URL` | No | `sqlite:///./geo_copilot.db` | Ruta SQLite |
| `CORS_ORIGINS` | No | `http://localhost:3000` | Orígenes del frontend (coma-separados) |

---

## CORS (frontend Next.js)

El backend acepta peticiones desde `http://localhost:3000` por defecto.

Si tu frontend corre en otro puerto, agrégalo en `.env`:

```env
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Desde el frontend:

```javascript
const res = await fetch("http://localhost:8000/health");
const data = await res.json(); // { status: "ok" }
```

---

## Endpoints

### Sistema

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Ping |

### Agente (ciclos unificados)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/agent/run-full-cycle` | Una URL: audit + probe + propuestas |
| POST | `/agent/run-site-cycle` | WordPress: audita todas las páginas + propuestas |

### Consultas

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/analyses` | Historial paginado |
| GET | `/analyses/{id}` | Detalle completo |
| GET | `/probe/results` | Historial de probes |
| GET | `/gsc/opportunities` | Oportunidades GSC mock |

### EDITAR / APRENDER

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/proposals` | Lista (`?status=pending`) |
| GET | `/proposals/review/next` | Cola editor + preview |
| GET | `/proposals/{id}/preview` | Preview HTML |
| POST | `/proposals/{id}/approve` | Publica en WordPress |
| POST | `/proposals/{id}/reject` | Rechaza con motivo |
| POST | `/proposals/{id}/measure-impact` | Re-medición mock |

---

## Flujo demo

### Sitio WordPress completo

```json
POST /agent/run-site-cycle
{ "include_posts": true }
```

### Una URL

```json
POST /agent/run-full-cycle
{ "url": "https://www.bancolombia.com/personas/blog" }
```

Luego: `GET /proposals/review/next` → approve/reject.

---

## Endpoints eliminados (v2.1)

`POST /analyze`, `/analyze/wordpress-pages`, `/agent/recommend`, `/agent/recommend-all`, `/probe/run` — reemplazados por los ciclos unificados. Ver `FRONTEND.md`.

---

## Stack

| Capa | Tecnología |
|---|---|
| API | FastAPI + Pydantic v2 |
| DB | SQLAlchemy 2.x + SQLite |
| LLM | Gemini 2.5 Flash |
| Scraping | requests + BeautifulSoup4 |
| Mocks | WordPress adapter, GSC, impact measurement |

---

## Notas para el pitch

- **Serfinanza.com.co** usa redirect JavaScript → el scraper con `requests` no ve el contenido real. Usa URLs scrapeables en demo (ej. blog Bancolombia) o menciona Playwright como fase 2.
- Los adapters mock (`wordpress_mock`, `gsc_mock`) tienen la misma interfaz que la integración real — swap en producción.
- Rate limit Gemini free tier: ~60 req/min. En demo usa 1 query en probe, no las 7.

---

## Estructura

```
app/
├── agents/          # auditor, recommender, orchestrator
├── models/          # SQLAlchemy (7 tablas)
├── routers/         # endpoints FastAPI
├── schemas/         # Pydantic request/response
├── services/        # scraper, scorer, gemini, probe, mocks
└── prompts/         # templates Gemini
```
