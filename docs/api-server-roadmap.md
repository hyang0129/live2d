# Live2D Render Server — Roadmap

FastAPI + Uvicorn HTTPS server that wraps the existing `live2d-render` CLI as a render service for director systems.

---

## Architecture

```
[Director / video_agent]
      │
      │  HTTPS (JSON)
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
      │  Rendered files on disk / presigned URL / download endpoint
      ▼
[Director retrieves output]
```

---

## Phase 1 — Models & Discovery (High Priority)

Expose the model registry so directors can discover available models and their cue vocabulary before building manifests.

### `GET /models`

List all registered models with summary info.

```json
// Response 200
[
  {
    "id": "shiori",
    "emotions": ["neutral", "curious", "angry", "sad", "happy", "surprised", "embarrassed", "bored"],
    "reactions": ["idle", "tap"]
  },
  {
    "id": "majo",
    "emotions": ["neutral", "happy", "surprised", "bored", "sad", "angry"],
    "reactions": ["idle"]
  }
]
```

**Implementation:** Read `assets/models/registry.json`, return `id` + emotion/reaction alias lists. No internal IDs (`F01`, `TapBody`) exposed.

### `GET /models/{model_id}`

Full detail for a single model, including the semantic notes that help a director LLM pick the right emotion.

```json
// Response 200
{
  "id": "shiori",
  "emotions": {
    "neutral":   "Resting face. Calm, composed default state.",
    "happy":     "Warm smile with softly closed eyes. Elevated joy.",
    "angry":     "Clear furrowed brow and narrowed eyes. Strong negative emotion.",
    "...": "..."
  },
  "reactions": {
    "idle": "Default idle animation loop. Subtle breathing and natural movement.",
    "tap":  "Reaction to a tap or touch interaction."
  }
}
```

Returns `404` if `model_id` not in registry.

**Implementation:** Same registry read, filtered to one entry. Return the `note` field values as descriptions — these are purpose-built for LLM consumption.

---

## Phase 2 — Render Jobs (High Priority)

Accept scene manifests, queue them, run `live2d-render` as a subprocess, and let the director poll for completion.

### `POST /renders`

Submit a render job. The request body is the scene manifest (same schema the CLI accepts), minus the `output` field — the server assigns that.

```json
// Request
{
  "schema_version": "1.0",
  "model": { "id": "shiori" },
  "audio_url": "https://storage.example.com/audio/scene_01.wav",
  "resolution": [1080, 1920],
  "fps": 30,
  "background": "transparent",
  "lipsync": [ ... ],
  "cues": [ ... ]
}
```

```json
// Response 202 Accepted
{
  "job_id": "r_01JQXYZ...",
  "status": "queued",
  "poll_url": "/renders/r_01JQXYZ...",
  "estimate_seconds": 120,
  "message": "Check back in ~2 minutes."
}
```

**Key decisions:**

| Decision | Choice | Rationale |
|---|---|---|
| Audio delivery | `audio_url` (server downloads) | Director shouldn't need to pre-stage files on the render host |
| Output path | Server-assigned under `renders/<job_id>/` | Prevents path traversal; clean per-job isolation |
| Job ID format | ULID or UUID | Sortable, no collisions |
| Sync vs async | Always async (202) | Even fast renders take 10+ seconds; never block the HTTP request |

**Workflow:**
1. Validate manifest schema (fail fast with 422 on bad input)
2. Download audio from `audio_url` to `renders/<job_id>/audio.wav`
3. Write manifest to `renders/<job_id>/manifest.json` (with server-assigned `output` path)
4. Enqueue job
5. Return 202 with `job_id` and time estimate

### `GET /renders/{job_id}`

Poll for job status.

```json
// Response 200 — still running
{
  "job_id": "r_01JQXYZ...",
  "status": "rendering",
  "progress": 0.45,
  "estimate_seconds": 65,
  "message": "Rendering frame 405/900. Check back in ~1 minute."
}
```

```json
// Response 200 — complete
{
  "job_id": "r_01JQXYZ...",
  "status": "complete",
  "output_url": "/renders/r_01JQXYZ.../output.mov",
  "duration_seconds": 98,
  "log_url": "/renders/r_01JQXYZ.../render.log"
}
```

```json
// Response 200 — failed
{
  "job_id": "r_01JQXYZ...",
  "status": "failed",
  "error": "Model 'nonexistent' not found in registry",
  "log_url": "/renders/r_01JQXYZ.../render.log"
}
```

**Status values:** `queued` → `downloading_audio` → `rendering` → `complete` | `failed`

### `GET /renders/{job_id}/output`

Download the rendered video file. Returns `404` if not yet complete, `410 Gone` if cleaned up.

### `GET /renders/{job_id}/log`

Download the render log. Available in all terminal states (complete/failed).

---

## Phase 3 — Job Execution Engine (High Priority)

The background machinery that actually runs render jobs.

### Worker pool

- `asyncio` task pool with configurable concurrency (default: 1 — GPU-bound, likely serialized)
- Each worker: download audio → write manifest → `subprocess.run(["./build/live2d-render", "--scene", manifest_path])` → update job state
- Capture stdout/stderr to `render.log`
- Parse renderer output for progress (frame count) to populate `progress` field

### Estimation

- Track historical render times per resolution/fps/duration
- Initial naive estimate: `(audio_duration_seconds / fps) * ms_per_frame_estimate`
- On poll: if job is in `rendering`, extrapolate from current frame progress
- Accuracy not critical — just give the director a ballpark so it can schedule its own work

### Storage & cleanup

- Render outputs stored under `renders/<job_id>/`
- Configurable TTL (default: 1 hour) — after which outputs are deleted
- Job metadata kept longer for debugging (24h default)

### Job persistence (v1: in-memory)

- `dict[str, Job]` in the FastAPI app state
- Acceptable for v1 — jobs are transient, renderer restarts are rare
- Future: SQLite or Redis if durability matters

---

## Phase 4 — Server Infrastructure (High Priority)

### HTTPS / TLS

- Uvicorn `--ssl-keyfile` / `--ssl-certfile` for TLS termination
- Or: run behind a reverse proxy (nginx/caddy) that handles TLS
- Self-signed certs acceptable for internal network; Let's Encrypt for public

### Configuration

Environment variables or `.env` file:

| Var | Default | Description |
|---|---|---|
| `RENDER_HOST` | `0.0.0.0` | Bind address |
| `RENDER_PORT` | `8443` | HTTPS port |
| `RENDER_WORKERS` | `1` | Max concurrent render jobs |
| `RENDER_BINARY` | `./build/live2d-render` | Path to renderer |
| `RENDER_OUTPUT_DIR` | `./renders` | Job output directory |
| `RENDER_OUTPUT_TTL` | `3600` | Seconds before cleaning up outputs |
| `TLS_CERT` | `certs/server.crt` | TLS certificate path |
| `TLS_KEY` | `certs/server.key` | TLS private key path |

### Health check

`GET /health` — returns 200 with renderer binary status, disk space, active job count.

### Auth (v1: API key)

Simple `Authorization: Bearer <key>` header check via FastAPI dependency. Single shared key from env var. Sufficient for internal service-to-service auth.

---

## Phase 5 — Web UI for Model Onboarding (Low Priority)

A browser UI for the human-in-the-loop model onboarding process defined in `docs/model-onboarding.md`.

### Scope

| Feature | Description |
|---|---|
| Model upload | Upload `.model3.json` + assets, assign an ASCII `id` |
| Checklist dashboard | Interactive pass/fail checklist (expressions, LipSync params, Idle motion, etc.) |
| Test render | Trigger a test render from the UI, preview the output video inline |
| Expression mapper | Visual tool to map model-internal expression names → semantic aliases (`happy`, `sad`, etc.) |
| Registry editor | Edit `registry.json` entries; add notes for each emotion/reaction |
| Rejection log | Record why a model was declined, with notes and date |

### Tech

- Served from the same FastAPI app under `/ui/`
- Jinja2 templates + HTMX (keep it simple, no SPA framework)
- Reuses the render job API for test renders

### Not in scope (for now)

- Multi-user auth / roles
- Automatic expression detection from model parameters
- Batch onboarding

---

## File & Module Layout

```
server/
├── __init__.py
├── main.py              # FastAPI app, lifespan, CORS, auth middleware
├── config.py            # Settings from env vars (pydantic-settings)
├── routers/
│   ├── models.py        # GET /models, GET /models/{id}
│   ├── renders.py       # POST /renders, GET /renders/{id}, output/log downloads
│   └── health.py        # GET /health
├── services/
│   ├── registry.py      # Load & query assets/models/registry.json
│   ├── job_manager.py   # Job queue, state machine, worker pool
│   └── renderer.py      # Subprocess wrapper for live2d-render CLI
├── schemas.py           # Pydantic models (manifest, job status, model info)
└── templates/           # Jinja2 templates for onboarding UI (Phase 5)
requirements.txt         # fastapi, uvicorn, pydantic-settings, python-multipart, httpx
```

---

## Implementation Order

| Step | What | Depends on |
|---|---|---|
| 1 | `config.py` + `schemas.py` + `main.py` scaffold | — |
| 2 | `registry.py` + `routers/models.py` | Step 1 |
| 3 | `routers/health.py` | Step 1 |
| 4 | `schemas.py` render job models | Step 1 |
| 5 | `renderer.py` subprocess wrapper | Step 1 |
| 6 | `job_manager.py` queue + worker pool | Steps 4, 5 |
| 7 | `routers/renders.py` | Steps 4, 6 |
| 8 | TLS setup + auth middleware | Step 1 |
| 9 | Onboarding UI | Steps 2, 7 |

Steps 2 and 3 can be done in parallel. Steps 5 and 4 can be done in parallel. Step 6 blocks on both.

---

## Open Questions

- **Audio delivery:** `audio_url` download vs multipart upload vs pre-staged path? Starting with URL download; can add multipart later.
- **Output delivery:** Direct file download vs pre-signed cloud URL? Starting with direct download; cloud storage is a future concern.
- **Concurrency:** Can the EGL headless renderer handle multiple simultaneous jobs? Need to test. Default to serial (1 worker) and scale up.
- **Webhook callback:** Should `POST /renders` accept an optional `callback_url` for push notification on completion? Nice-to-have — polling works fine for v1.
