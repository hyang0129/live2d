# Live2D Render Server — API Reference

FastAPI + Uvicorn HTTPS service that wraps the `live2d-render` CLI for use by director systems.

## Running the server

```bash
source .venv/bin/activate
uvicorn server.main:app --host 0.0.0.0 --port 8443 \
  --ssl-keyfile certs/server.key --ssl-certfile certs/server.crt
```

**Development (HTTP, no TLS):**
```bash
uvicorn server.main:app --host 127.0.0.1 --port 8080
```

## Configuration

All settings are environment variables (or `.env` file at the project root).

| Variable | Default | Description |
|---|---|---|
| `RENDER_HOST` | `0.0.0.0` | Bind address |
| `RENDER_PORT` | `8443` | HTTPS port |
| `RENDER_WORKERS` | `1` | Max concurrent render jobs (GPU-bound — start at 1) |
| `RENDER_BINARY` | `./build/live2d-render` | Path to the renderer CLI |
| `RENDER_OUTPUT_DIR` | `./renders` | Directory for job output files |
| `RENDER_OUTPUT_TTL` | `3600` | Seconds before job outputs are cleaned up |
| `REGISTRY_PATH` | `./assets/models/registry.json` | Path to the model registry |
| `TLS_CERT` | `certs/server.crt` | TLS certificate |
| `TLS_KEY` | `certs/server.key` | TLS private key |
| `API_KEY` | *(empty)* | Bearer token for auth. Empty = auth disabled |

## Authentication

When `API_KEY` is set, all requests (except `GET /health`) must include:

```
Authorization: Bearer <key>
```

Returns `401` if missing or incorrect.

---

## Endpoints

### `GET /health`

Server and renderer status. Always public (no auth required).

**Response 200:**
```json
{
  "status": "ok",
  "renderer_available": true,
  "disk_free_gb": 42.3,
  "active_jobs": 1,
  "queued_jobs": 0
}
```

| Field | Description |
|---|---|
| `renderer_available` | Whether `./build/live2d-render` exists on disk |
| `disk_free_gb` | Free disk on the output directory filesystem |
| `active_jobs` | Jobs currently rendering |
| `queued_jobs` | Jobs waiting to start |

---

### `GET /models`

List all registered models with their emotion and reaction alias names.

**Response 200:**
```json
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

---

### `GET /models/{model_id}`

Full detail for one model, including semantic notes for each emotion and reaction. These notes are written for LLM consumption — they describe when to use each expression.

**Path params:**
- `model_id` — model ID as it appears in the registry (e.g. `shiori`, `majo`)

**Response 200:**
```json
{
  "id": "shiori",
  "emotions": {
    "neutral":     "Resting face. Calm, composed default state. Use as a reset between other expressions.",
    "happy":       "Warm smile with softly closed eyes. Elevated joy — more intense than a neutral smile.",
    "angry":       "Clear furrowed brow and narrowed eyes. Strong negative emotion.",
    "sad":         "Downcast eyes and softened features. Use for disappointment, empathy, or somber moments.",
    "curious":     "Neutral face with slightly raised eyebrows. Conveys mild interest or attentiveness.",
    "surprised":   "Wide open eyes. Use for unexpected reveals or sudden reactions.",
    "embarrassed": "Flustered expression. Use for awkward situations or self-conscious moments.",
    "bored":       "Heavy-lidded, uninterested look. Use to convey disengagement or mild disdain."
  },
  "reactions": {
    "idle": "Default idle animation loop. Subtle breathing and natural movement.",
    "tap":  "Reaction to a tap or touch interaction. Brief startled or responsive motion."
  }
}
```

**Response 404** — model ID not in registry:
```json
{ "detail": "Model 'unknown' not found" }
```

---

### `POST /renders`

Submit a render job. The server downloads the audio, writes the CLI manifest, and queues the job. Always returns `202 Accepted` — renders are always asynchronous.

**Request body:**
```json
{
  "schema_version": "1.0",
  "model": { "id": "shiori" },
  "audio_url": "https://storage.example.com/audio/scene_01.wav",
  "resolution": [1080, 1920],
  "fps": 30,
  "background": "transparent",
  "lipsync": [
    { "time": 0.0,  "mouth_shape": "X" },
    { "time": 0.15, "mouth_shape": "C" },
    { "time": 0.22, "mouth_shape": "E" }
  ],
  "cues": [
    { "time": 0.0, "emotion": "neutral" },
    { "time": 2.5, "emotion": "happy" },
    { "time": 4.0, "reaction": "tap" },
    { "time": 5.0, "gaze": { "x": 0.3, "y": -0.1 } },
    { "time": 6.0, "head": { "yaw": 15.0, "pitch": -5.0, "roll": 0.0 } }
  ]
}
```

**Fields:**

| Field | Required | Description |
|---|---|---|
| `model.id` | Yes | Model ID from the registry |
| `audio_url` | Yes | HTTP/HTTPS URL to a WAV file. Server downloads it. |
| `resolution` | No | `[width, height]` in pixels. Default: `[1080, 1920]` |
| `fps` | No | Frames per second. Default: `30` |
| `background` | No | `"transparent"`, `"#RRGGBB"` hex color, or image path. Default: `"transparent"` |
| `lipsync` | No | Timed mouth shape keyframes |
| `cues` | No | Timed directives: emotion, reaction, gaze, or head angle |

**Mouth shapes** (`lipsync[].mouth_shape`): `A` `B` `C` `D` `E` `F` `G` `H` `X` (X = closed/rest)

**Cue types** (mutually exclusive per cue object):
- `emotion: "<alias>"` — set expression (must be in the model's emotion list)
- `reaction: "<alias>"` — trigger motion (must be in the model's reaction list)
- `gaze: { "x": float, "y": float }` — eye gaze direction, range `[-1.0, 1.0]`
- `head: { "yaw": float, "pitch": float, "roll": float }` — head angle in degrees

**Response 202:**
```json
{
  "job_id": "r_2ecfd9a381c84df580a753744a5720c7",
  "status": "queued",
  "poll_url": "/renders/r_2ecfd9a381c84df580a753744a5720c7",
  "estimate_seconds": 120,
  "message": "Check back in ~2 minutes."
}
```

**Response 422** — validation failure:
```json
{ "detail": "Model 'nonexistent' not found in registry" }
```

---

### `GET /renders/{job_id}`

Poll for job status.

**Path params:**
- `job_id` — job ID returned by `POST /renders`

**Response 200 — queued or downloading:**
```json
{
  "job_id": "r_2ecfd9a381c84df580a753744a5720c7",
  "status": "queued"
}
```

**Response 200 — rendering:**
```json
{
  "job_id": "r_2ecfd9a381c84df580a753744a5720c7",
  "status": "rendering",
  "progress": 0.45,
  "estimate_seconds": 65,
  "message": "Rendering — 45% complete. Check back in ~65s."
}
```

**Response 200 — complete:**
```json
{
  "job_id": "r_2ecfd9a381c84df580a753744a5720c7",
  "status": "complete",
  "output_url": "/renders/r_2ecfd9a381c84df580a753744a5720c7/output",
  "log_url": "/renders/r_2ecfd9a381c84df580a753744a5720c7/log",
  "duration_seconds": 35.5
}
```

**Response 200 — failed:**
```json
{
  "job_id": "r_2ecfd9a381c84df580a753744a5720c7",
  "status": "failed",
  "error": "Renderer exited with code 3. Last output:\n[ERROR] Model 'shiori' expression 'F99' not found",
  "log_url": "/renders/r_2ecfd9a381c84df580a753744a5720c7/log"
}
```

**Status flow:** `queued` → `downloading_audio` → `rendering` → `complete` | `failed`

**Response 404** — unknown job ID.

---

### `GET /renders/{job_id}/output`

Download the rendered video file (MP4).

- Returns `404` if the job is not yet complete or the ID is unknown.
- Returns `410 Gone` if the output has been cleaned up (past TTL).
- Content-Type: `video/mp4`

---

### `GET /renders/{job_id}/log`

Download the full render log (stdout + stderr from the renderer process).

Available in any terminal state (`complete` or `failed`). Returns `404` if the job hasn't started rendering yet.

- Content-Type: `text/plain`

---

## Polling pattern

```python
import httpx, time

resp = httpx.post("https://render.internal/renders", json=manifest)
job_id = resp.json()["job_id"]

while True:
    status = httpx.get(f"https://render.internal/renders/{job_id}").json()
    if status["status"] == "complete":
        video = httpx.get(f"https://render.internal{status['output_url']}")
        break
    elif status["status"] == "failed":
        raise RuntimeError(status["error"])
    time.sleep(5)
```

## Local test

```bash
# Direct CLI (no server, fastest)
python3 test_render.py --direct --scene 1

# Full server stack (HTTP, scene 1-6)
python3 test_render.py --scene 1
```
