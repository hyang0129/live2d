# Live2D Render Server — Roadmap

FastAPI + Uvicorn server that wraps the `live2d-render` CLI as a render service for director systems.

---

## Architecture

```
[Director / video_agent]
      │
      │  HTTP/S (JSON)
      ▼
┌──────────────────────────────────┐
│  FastAPI Server (Uvicorn)        │
│                                  │
│  ┌────────────┐  ┌────────────┐  │
│  │ Model API  │  │ Render API │  │
│  │ (registry) │  │ (jobs)     │  │
│  └────────────┘  └─────┬──────┘  │
│                        │         │
│              ┌─────────▼───────┐ │
│              │  Job Queue      │ │
│              │  (in-process)   │ │
│              └─────────┬───────┘ │
│                        │         │
│              ┌─────────▼───────┐ │
│              │  Worker Pool    │ │
│              │  (subprocess    │ │
│              │   live2d-render)│ │
│              └─────────────────┘ │
└──────────────────────────────────┘
      │
      │  File download / output_url
      ▼
[Director retrieves output]
```

---

## Status Legend

| Symbol | Meaning |
|---|---|
| ✅ | Done and working |
| 🔧 | Done, known gaps / minor issues remain |
| ❌ | Not started |
| ⚠️ | Partial |

---

## Phase 1 — Models & Discovery ✅

**All endpoints implemented and operational.**

| Item | Status | Notes |
|---|---|---|
| `GET /models` — list all models | ✅ | Reads registry, returns id + emotion/reaction alias lists |
| `GET /models/{id}` — model detail | ✅ | Returns semantic notes for LLM consumption; 404 on unknown |
| `registry.py` — file I/O error handling | ✅ | Wraps `open()` + `json.load()` in try/except with descriptive errors |
| `registry.py` — defensive `.get("note", "")` | ✅ | No KeyError if registry entry is missing note field |

---

## Phase 2 — Render Jobs ✅

**All endpoints implemented and operational.**

| Item | Status | Notes |
|---|---|---|
| `POST /renders` — submit job | ✅ | Validates model ID, enqueues, returns 202 + job_id |
| `GET /renders/{id}` — poll status | ✅ | Returns status/progress/estimate, output_url on complete, error on fail |
| `GET /renders/{id}/output` — download video | ✅ | 404 if not complete, 410 if TTL expired |
| `GET /renders/{id}/log` — download log | ✅ | Available in complete or failed states |
| Audio download via `audio_url` | ✅ | httpx download to `renders/<job_id>/audio.wav` |
| Server-assigned output path | ✅ | `renders/<job_id>/output.mp4` |
| Model ID validation before enqueue | ✅ | 422 with clear message if model not in registry |

---

## Phase 3 — Job Execution Engine ✅

**Core machinery working; minor hardening gaps remain.**

| Item | Status | Notes |
|---|---|---|
| asyncio worker pool | ✅ | Configurable concurrency via `RENDER_WORKERS` |
| Audio download → manifest write → subprocess | ✅ | Full pipeline in `job_manager._run_job()` |
| `renderer.py` subprocess wrapper | ✅ | Async subprocess, streams stdout for progress, captures full log |
| Frame progress parsing | ✅ | Parses `Frame N/M` from renderer stdout |
| Progress-based time estimate | ✅ | Fixed divide-by-zero (progress > 0 guard); accurate once rendering starts |
| Status machine | ✅ | `queued → downloading_audio → rendering → complete\|failed` |
| Per-job directory isolation | ✅ | `renders/<job_id>/` — manifest, audio, output, log |
| Worker unhandled exception safety | 🔧 | Outer try/except exists but worker crash doesn't restart worker |
| Audio download timeout | 🔧 | Hardcoded 60s; not configurable via env var |
| Output TTL / cleanup | ❌ | Outputs accumulate forever; no cleanup task implemented |
| Job metadata retention | ❌ | In-memory only — lost on server restart |

---

## Phase 4 — Server Infrastructure ✅

**Fully operational. A few hardening items remain.**

| Item | Status | Notes |
|---|---|---|
| FastAPI app + lifespan | ✅ | Worker pool start/stop in lifespan |
| `pydantic-settings` config | ✅ | All tunables via env vars / `.env` |
| `GET /health` | ✅ | Binary availability, disk space, active/queued counts; async |
| Bearer token auth middleware | ✅ | All routes except `/health` protected; disabled if `API_KEY` unset |
| CORS | ✅ | Permissive (`*`) — tighten for production |
| TLS | 🔧 | Uvicorn supports `--ssl-*` flags but no certs generated/documented in repo |
| `.gitignore` — `renders/` excluded | ✅ | Job outputs not tracked in git |
| `.gitignore` — `.venv/` excluded | ✅ | |
| Startup validation of binary/registry | ❌ | Server starts even if binary or registry is missing; only fails at request time |
| Auth middleware public path list | 🔧 | Hardcoded `/health` exclusion — needs a config list for extensibility |
| Request logging | ❌ | No structured access log |
| Rate limiting | ❌ | No per-client rate limiting |

---

## Phase 5 — Web UI for Model Onboarding ❌

Not started. Low priority. See original design in this file's git history.

| Feature | Status |
|---|---|
| Model upload | ❌ |
| Expression checklist dashboard | ❌ |
| Test render + inline preview | ❌ |
| Expression mapper (internal ID → alias) | ❌ |
| Registry editor | ❌ |
| Rejection log | ❌ |

Tech plan: FastAPI + Jinja2 + HTMX, served under `/ui/`. Reuses the render job API for test renders.

---

## Remaining Gaps (Priority Order)

### P1 — Correctness / Reliability

| Gap | Where | Fix |
|---|---|---|
| Output TTL cleanup task | `job_manager.py` | `asyncio.create_task` background loop that deletes job dirs past TTL |
| Worker crash recovery | `job_manager.py:_worker()` | Wrap outer loop in try/except; restart dead workers |
| Startup validation | `main.py` lifespan | Check `binary_path.exists()` and registry readable; log warning or raise |

### P2 — Operability

| Gap | Where | Fix |
|---|---|---|
| Structured access logging | `main.py` | Add `logging` middleware or use `uvicorn.access` config |
| Configurable audio timeout | `config.py` + `job_manager.py` | Add `AUDIO_DOWNLOAD_TIMEOUT` setting |
| TLS certs in dev | `docs/` | Document `mkcert` workflow; add `certs/` to `.gitignore` |
| Job persistence across restarts | `job_manager.py` | SQLite via `aiosqlite` (lightweight; no external deps) |

### P3 — Security / Hardening (pre-production)

| Gap | Where | Fix |
|---|---|---|
| SSRF on `audio_url` | `job_manager.py` | Validate URL is not RFC1918 / loopback before downloading |
| CORS lockdown | `main.py` | Replace `*` with explicit origin allowlist |
| Auth public path list | `main.py` | Replace hardcoded `/health` exclusion with `settings.public_paths` |
| Rate limiting | `main.py` | `slowapi` or nginx-level limit |

---

## Open Questions

- **Webhook callback:** Should `POST /renders` accept an optional `callback_url` for push notification on completion? Polling works fine for v1; webhook is a nice-to-have for latency-sensitive directors.
- **Concurrency:** Can the EGL headless renderer handle multiple simultaneous jobs? Defaulting to 1 worker — test before raising `RENDER_WORKERS`.
- **Output delivery:** Direct file download vs pre-signed cloud URL? Current: direct download. Cloud storage upgrade path exists but not needed until horizontal scaling.
- **Job persistence:** In-memory is fine for a single-process renderer. If we ever run multiple server instances or need restart durability, add SQLite (`aiosqlite`).

---

## File Layout

```
server/
├── main.py              ✅  FastAPI app, lifespan, auth middleware
├── config.py            ✅  pydantic-settings env config
├── schemas.py           ✅  Pydantic models (manifest, job, model info)
├── routers/
│   ├── health.py        ✅  GET /health
│   ├── models.py        ✅  GET /models, GET /models/{id}
│   └── renders.py       ✅  POST /renders, GET /renders/{id}, output/log
├── services/
│   ├── registry.py      ✅  Load/query assets/models/registry.json
│   ├── job_manager.py   ✅  Job queue, state machine, worker pool
│   └── renderer.py      ✅  Async subprocess wrapper for live2d-render
└── templates/           ❌  Jinja2 for onboarding UI (Phase 5)
docs/
├── api-server.md        ✅  Full API reference (generated)
└── api-server-roadmap.md    This file
```
