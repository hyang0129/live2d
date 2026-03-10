# Live2D Avatar Renderer

A CLI that takes direction from an orchestrating system and renders a Live2D avatar to video.

---

## Mental Model

Think of this project as an **actor**, not a director.

| Role | System | Responsibilities |
|---|---|---|
| **Director** | External orchestrator (`video_agent`) | Script, voice-over audio, Rhubarb lipsync analysis, emotional cues, timing |
| **Actor** | This project | Interpret those directions and render the performance to video |

The orchestrating system decides *what* happens and provides a fully-specified manifest. This system renders it — no analysis or inference of its own.

---

## Inputs

The renderer accepts a **scene manifest** — a structured JSON description of a single continuous take:

```json
{
  "schema_version": "1.0",
  "model": {
    "id": "shiori",
    "path": "assets/models/shiori/shiori.model3.json"
  },
  "audio": "path/to/voiceover.wav",
  "output": "path/to/output.mp4",
  "resolution": [1080, 1920],
  "fps": 30,
  "background": "transparent",
  "lipsync": [
    { "time": 0.00, "mouth_shape": "X" },
    { "time": 0.15, "mouth_shape": "C" },
    { "time": 0.29, "mouth_shape": "B" }
  ],
  "cues": [
    { "time": 0.0, "emotion": "neutral" },
    { "time": 1.2, "emotion": "happy" },
    { "time": 3.5, "reaction": "nod" }
  ]
}
```

| Field | Description |
|---|---|
| `schema_version` | Must be `"1.0"` |
| `model.id` | Model ID looked up in `assets/models/registry.json` |
| `model.path` | Fallback path to `.model3.json` if `id` is not in the registry |
| `audio` | Voice-over WAV file — mixed into the output video |
| `output` | Destination video file (`.mp4` or `.mov`) |
| `resolution` | `[width, height]` in pixels |
| `fps` | Target frame rate |
| `background` | `"transparent"`, `"#RRGGBB"` color, or path to an image |
| `lipsync` | Pre-computed Rhubarb mouth-shape keyframes (generated upstream by `video_agent`) |
| `cues` | Timed directives — emotions, reactions, gaze, and head angles |

---

## Outputs

For each scene, the renderer writes two files to the output directory:

| File | Description |
|---|---|
| `scene.mov` / `scene.mp4` | Rendered video with lip sync, expressions, physics, and audio mixed in |
| `scene.log` | Full render log — all INFO, WARN, and ERROR lines for that take |

**Container selection:**
- `"background": "transparent"` → ProRes 4444 in `.mov` (RGBA alpha channel)
- Opaque background → H.264 in `.mp4`
- If the manifest specifies `.mp4` with a transparent background, the renderer auto-corrects to `.mov` and emits a `WARN`.

The log file is the primary feedback channel back to the director. `WARN` lines indicate silent failures — directions the renderer received but could not fully execute (e.g. an emotion name not defined on the model).

---

## What This System Does NOT Do

- Generate scripts or dialogue
- Generate or process audio (TTS, voice cloning, etc.)
- Analyze audio for lip sync — Rhubarb keyframes are provided in the manifest
- Decide which emotions or reactions to use
- Orchestrate multi-scene sequences

All of that belongs to the upstream director system.

---

## Architecture

```
[Director System / video_agent]
      │
      │  scene manifest (JSON) + pre-computed Rhubarb lipsync
      ▼
┌─────────────────────────────────┐
│         Renderer CLI            │
│                                 │
│  ┌──────────────┐  ┌──────────┐ │
│  │  Lipsync     │  │  Cue     │ │
│  │  Sequencer   │  │ Sequencer│ │
│  │ (keyframes)  │  │ (timed)  │ │
│  └──────┬───────┘  └────┬─────┘ │
│         │               │       │
│         └───────┬───────┘       │
│                 ▼               │
│  ┌──────────────────────────┐   │
│  │   Live2D Model Engine    │   │
│  │  (Cubism Native SDK 5)   │   │
│  └────────────┬─────────────┘   │
│               │                 │
│               ▼                 │
│  ┌──────────────────────────┐   │
│  │   Offscreen Renderer     │   │
│  │   (D3D11, no window)     │   │
│  └────────────┬─────────────┘   │
│               │                 │
│               ▼                 │
│  ┌──────────────────────────┐   │
│  │    Video Encoder         │   │
│  │    (FFmpeg child proc)   │   │
│  └──────────────────────────┘   │
└─────────────────────────────────┘
      │
      │  scene.mov + scene.log
      ▼
[Director System / Final Delivery]
```

---

## CLI Usage

```bash
# Render a single take
live2d-render --scene scene.json

# Override output path
live2d-render --scene scene.json --output take_02.mp4

# Render with transparent background (forces .mov container)
live2d-render --scene scene.json --transparent

# Set log verbosity (error | warn | info | debug)
live2d-render --scene scene.json --log-level debug
```

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Bad arguments |
| `2` | Manifest parse/validation error |
| `3` | Asset not found (model, audio) |
| `4` | Render error |
| `5` | Output/encode error |

---

## Cue Types

Cues are the primary interface between the director and this system. The supported cue types define the actor's vocabulary.

| Cue type | Description | Example value |
|---|---|---|
| `emotion` | Facial expression — must be an alias defined in the model registry | `"happy"`, `"sad"`, `"neutral"` |
| `reaction` | Short motion clip — must be an alias defined in the model registry | `"tap"`, `"idle"` |
| `gaze` | Eye direction override | `{ "x": 0.5, "y": -0.2 }` |
| `head` | Head angle override | `{ "yaw": 10, "pitch": -5, "roll": 0 }` |

Valid `emotion` and `reaction` values are defined per-model in the registry (see below). Any name not in the registry produces a `WARN` in the log and is silently skipped — the renderer never exposes raw model-internal names (e.g. `F01`, `TapBody`) to the director.

---

## Model Registry

`assets/models/registry.json` is the single source of truth for:
- Which models are available and where their `.model3.json` files are
- The complete **cue vocabulary** the director is allowed to use for each model

Each entry maps semantic alias names (used in manifests) to raw model-internal names (Live2D expression/motion group names). The director only ever sees and uses the alias names.

```json
{
  "id": "shiori",
  "path": "cubism/Samples/Resources/Haru/Haru.model3.json",
  "emotions": {
    "neutral":     "F01",
    "happy":       "F02",
    "sad":         "F03",
    "surprised":   "F04",
    "angry":       "F05",
    "embarrassed": "F06",
    "troubled":    "F07",
    "shy":         "F08"
  },
  "reactions": {
    "idle": "Idle",
    "tap":  "TapBody"
  }
}
```

### Discovering the vocabulary

Before authoring manifests, the director queries the renderer for a model's available cues:

```bash
live2d-render --inspect --model shiori
```

```json
{
  "model": "shiori",
  "path": "cubism/Samples/Resources/Haru/Haru.model3.json",
  "emotions": ["angry", "embarrassed", "happy", "neutral", "sad", "shy", "surprised", "troubled"],
  "reactions": ["idle", "tap"]
}
```

The output lists only the alias names — these are the exact strings the director may use in `"emotion"` and `"reaction"` cue fields.

### Adding a new model

Not every model is compatible with this renderer. A model must have facial expressions, populated LipSync/EyeBlink parameter groups, and a named Idle motion group before it can be registered.

All registry `id` values must be lowercase ASCII (e.g. `"sparkle"`, `"shiori"`). If the model's directory or files use non-ASCII names (e.g. `魔女/魔女.model3.json`), the human must supply a plain ASCII identifier before onboarding can proceed.

See [docs/model-onboarding.md](docs/model-onboarding.md) for the full evaluation checklist — including pass/fail criteria, the test-render workflow, and the rejection log for models that were evaluated and declined.

---

## Development Stack

| Component | Technology |
|---|---|
| Model rendering | Live2D Cubism Native SDK 5-r.4.1 |
| Graphics backend | D3D11 (headless, no window or swap chain) |
| Lip sync | Pre-computed Rhubarb keyframes → `ParamMouthOpenY` / `ParamMouthForm` |
| Video encoding | FFmpeg (child process, frames piped via stdin) |
| Build system | CMake 3.16+ + Visual Studio 2022 |
| Platform | Windows 10/11 |

---

## Building

```bash
cmake -S . -B build
cmake --build build --config Release
# binary: build/Release/live2d-render.exe
```

Run from the project root — shader and asset paths are relative to the working directory.

---

## API Contract

The full interface contract — scene manifest schema, lipsync vocabulary, cue types, model selection, and CLI specification — is defined in [docs/live2d-avatar-api-contract.md](docs/live2d-avatar-api-contract.md).

---

## Related

- [SDK_README.md](SDK_README.md) — Live2D Cubism SDK reference (internal rendering layer)
- [docs/cli_design.md](docs/cli_design.md) — Component design and data flow
