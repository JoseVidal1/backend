# GEO Copilot — Guía Frontend (API simplificada v2.1)

**Base URL:** `http://localhost:8000` · **Swagger:** `/docs` · **Sin auth**

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Flujo simplificado — solo 2 endpoints de acción

| Caso | Endpoint | Qué hace |
|---|---|---|
| **Una URL** | `POST /agent/run-full-cycle` | Scrape + probe + propuestas |
| **Sitio WordPress** | `POST /agent/run-site-cycle` | Audita todas las páginas + propuestas |

Luego el editor usa los endpoints de **propuestas** (preview, approve, reject).

---

## 1. Una URL — `POST /agent/run-full-cycle`

**Request:**
```json
{ "url": "https://bancolombia.com/personas/blog" }
```

**Response:**
```json
{
  "analysis_id": 21,
  "url": "https://...",
  "seo_score": 72,
  "geo_score": 45,
  "probe_results_count": 2,
  "proposals_count": 5,
  "scrape_summary": { "title": "...", "word_count": 450 },
  "scrape_warning": null,
  "proposals": [{ "id": 40, "proposal_type": "BLOG_POST", "status": "pending" }]
}
```

Tiempo: 30–90 s. Mostrar loading.

---

## 2. Sitio WordPress — `POST /agent/run-site-cycle`

**Request:**
```json
{
  "wordpress_url": "https://wordpress-production-d55e.up.railway.app",
  "include_posts": true,
  "status": "publish",
  "skip_existing": true
}
```

Body vacío `{}` usa defaults + `WORDPRESS_URL` del backend.

**Response:**
```json
{
  "source": "https://...",
  "total_found": 4,
  "analyzed": 4,
  "audit_failed": 0,
  "audit_results": [
    { "analysis_id": 21, "url": "...", "wp_title": "...", "seo_score": 60, "geo_score": 20, "status": "completed" }
  ],
  "processed": 2,
  "skipped": 2,
  "recommend_failed": 0,
  "total_proposals_created": 10,
  "recommend_results": [
    { "analysis_id": 21, "url": "...", "proposals_created": 5, "proposals": [...], "skipped": false }
  ]
}
```

Tiempo: 1–5 min. Mostrar loading.

---

## 3. Editor — revisión de propuestas

| Método | Ruta | Uso |
|---|---|---|
| GET | `/proposals?status=pending` | Lista cola de revisión |
| GET | `/proposals/review/next` | Siguiente pendiente + preview HTML |
| GET | `/proposals/{id}/preview` | Preview de una específica |
| POST | `/proposals/{id}/approve` | Publica en WordPress |
| POST | `/proposals/{id}/reject` | `{ "reason": "..." }` |
| POST | `/proposals/{id}/measure-impact` | Impacto (solo approved) |

**Preview response (campos clave):**
- `content_html` → renderizar en editor
- `can_review` → habilitar botones
- `pending_count` → contador cola

---

## 4. Consultas (solo lectura)

| Método | Ruta | Uso |
|---|---|---|
| GET | `/health` | Ping |
| GET | `/analyses` | Historial auditorías (`?status=completed`) |
| GET | `/analyses/{id}` | Detalle análisis |
| GET | `/probe/results` | Historial probes |
| GET | `/gsc/opportunities` | Oportunidades GSC mock |

---

## Flujo completo demo

```
POST /agent/run-site-cycle     → audita + propuestas
GET  /proposals/review/next    → editor preview
POST /proposals/{id}/approve   → publica
POST /proposals/{id}/measure-impact
```

---

## Reglas importantes

1. **`GET /analyses?status=pending`** → casi siempre vacío. Usar **`GET /proposals?status=pending`** para cola editor.
2. Listados paginados: `{ items: [], total, limit, offset }`
3. Error **429** = cuota Gemini agotada
4. Si `scrape_warning` tiene texto → mostrar banner

---

## Enums TypeScript

```typescript
type AnalysisStatus = "pending" | "completed" | "failed"
type ProposalStatus = "pending" | "approved" | "rejected"
type ProposalType = "BLOG_POST" | "META_DESCRIPTION" | "FAQ_SCHEMA" | "ALT_TEXT_FIX" | "SCHEMA_MARKUP" | "GEO_INSIGHT"
type Severity = "high" | "medium" | "low"
```

Generar tipos: `npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts`

---

## Endpoints eliminados (usar ciclos)

| Antes | Ahora |
|---|---|
| `POST /analyze` | `POST /agent/run-full-cycle` |
| `POST /analyze/wordpress-pages` | `POST /agent/run-site-cycle` |
| `POST /agent/recommend` | incluido en ciclos |
| `POST /agent/recommend-all` | incluido en run-site-cycle |
| `POST /probe/run` | incluido en run-full-cycle |
