# CLI Design — live2d-render

## Overview

`live2d-render` is the single entry point for the renderer. It accepts a scene
manifest from the upstream orchestrator, validates all inputs, drives the
rendering pipeline, and writes the output video. It has no interactive mode —
every invocation is a single-shot render job.

---

## Command Interface

```
live2d-render --scene <path> [--output <path>] [--transparent] [--log-level <level>]
```

### Arguments

| Argument | Type | Required | Description |
|---|---|---|---|
| `--scene <path>` | string | yes | Path to the scene manifest JSON |
| `--output <path>` | string | no | Override the `output` field in the manifest |
| `--transparent` | flag | no | Override `background` to `"transparent"` |
| `--log-level <level>` | string | no | Verbosity: `error`, `warn`, `info` (default), `debug` |

### Exit Codes

| Code | Meaning |
|---|---|
| `0` | Render succeeded; output file written |
| `1` | Invalid arguments or missing required flag |
| `2` | Manifest validation failure (bad schema, missing fields, unknown version) |
| `3` | Asset resolution failure (model not found, audio file missing) |
| `4` | Render failure (D3D11/OpenGL error, frame encode failure) |
| `5` | Output write failure (disk full, bad output path) |

Output is written **only** on exit code 0. A partial or failed render never
produces an output file.

---

## Startup Sequence

```
1. Parse CLI arguments
2. Load and validate scene manifest
3. Resolve model path (registry → path fallback)
4. Verify audio file exists and is readable
5. Initialize graphics backend (D3D11 / OpenGL)
6. Load Live2D model into Cubism engine
7. Prepare render target (offscreen framebuffer)
8. Execute render loop
9. Finalize video via FFmpeg
10. Write output file atomically (temp file → rename)
11. Exit 0
```

Any failure at steps 2–10 logs a clear error message to stderr and exits with
the appropriate non-zero code.

---

## Component Breakdown

### 1. Argument Parser (`cli/args.cpp`)

Responsibilities:
- Parse `argc`/`argv` using a minimal argument parser (no third-party lib required)
- Validate that `--scene` is provided
- Produce an `Args` struct consumed by the rest of the pipeline

```cpp
struct Args {
    std::string scene_path;
    std::string output_override;  // empty if not set
    bool transparent_override;    // false if not set
    LogLevel log_level;
};
```

### 2. Manifest Loader (`cli/manifest.cpp`)

Responsibilities:
- Read and parse the scene manifest JSON
- Validate `schema_version` (reject unknown versions with exit 2)
- Validate required fields: `model`, `audio`, `output`, `resolution`, `fps`
- Apply CLI overrides: `--output` and `--transparent`
- Produce a `SceneManifest` struct

```cpp
struct SceneManifest {
    std::string schema_version;
    ModelSpec   model;
    std::string audio_path;
    std::string output_path;
    int         width, height;
    int         fps;
    Background  background;        // transparent | color | image path
    std::vector<LipsyncKeyframe> lipsync;
    std::vector<Cue>             cues;
};
```

Unknown top-level fields and unknown cue keys are silently ignored (forward
compatibility per contract).

### 3. Model Resolver (`cli/model_resolver.cpp`)

Responsibilities:
- Load `assets/models/registry.json`
- Look up manifest `model.id` in the registry
- Fall back to `model.path` if `id` is not registered
- Return the resolved `.model3.json` path, or exit 3 with a clear error

```
Resolution order:
  registry[model.id].path  →  model.path  →  exit 3
```

### 4. Lipsync Sequencer (`render/lipsync_sequencer.cpp`)

Responsibilities:
- Hold the sorted `lipsync` keyframe array
- At each frame time `t`, interpolate between adjacent keyframes to produce a
  `MouthState` (set of Live2D mouth parameter values)
- Map Rhubarb shape codes to `ParamMouthOpenY` / `ParamMouthForm` values

Rhubarb → Live2D parameter mapping:

| Shape | `ParamMouthOpenY` | `ParamMouthForm` | Notes |
|---|---|---|---|
| `X` | 0.0 | 0.0 | Closed / rest |
| `A` | 0.1 | -1.0 | Lips pressed |
| `B` | 1.0 | 0.0 | Wide open |
| `C` | 0.8 | 0.5 | Rounded open |
| `D` | 0.3 | 0.0 | Slight open |
| `E` | 0.6 | 0.5 | Rounded mid |
| `F` | 0.2 | -0.5 | Top teeth |
| `G` | 0.4 | 0.0 | Tongue near teeth |
| `H` | 0.3 | 0.3 | Slight open / rounded |

Interpolation is linear between adjacent keyframe times.

### 5. Cue Sequencer (`render/cue_sequencer.cpp`)

Responsibilities:
- Hold the sorted `cues` array
- Dispatch pending cues each frame as time advances
- For `emotion`: call `model->SetExpression(name)` with blend
- For `reaction`: call `model->StartMotion(name)`
- For `gaze`: set `ParamEyeBallX` / `ParamEyeBallY` directly
- For `head`: set `ParamAngleX` / `ParamAngleY` / `ParamAngleZ` directly
- Silently ignore unrecognized cue keys

State machine per cue type:

```
emotion: IDLE → BLENDING (transition_ms=300) → HELD
reaction: IDLE → PLAYING (until motion clip ends) → IDLE
gaze/head: apply immediately, held until next cue of same type
```

### 6. Render Loop (`render/render_loop.cpp`)

Responsibilities:
- Drive frame-accurate rendering at the manifest `fps`
- Each frame:
  1. Advance scene time by `1/fps` seconds
  2. Dispatch pending cues (CueSequencer)
  3. Compute mouth state (LipsyncSequencer)
  4. Update Live2D model (physics tick, parameter write)
  5. Draw model to offscreen framebuffer
  6. Read back pixel data (RGBA)
  7. Send frame to FFmpeg encoder

Frame time is computed deterministically from frame index (`frame / fps`), not
wall-clock time. This ensures reproducible output.

### 7. Offscreen Renderer (`render/offscreen_d3d11.cpp` / `render/offscreen_opengl.cpp`)

Responsibilities:
- Create an offscreen render target at the specified resolution
- No window or swap chain — pure headless rendering
- Provide a `ReadPixels(buffer)` method for frame readback
- Handle transparent background (RGBA clear color `0,0,0,0`) vs solid color

Backend selection:
- D3D11 is the default on Windows
- OpenGL fallback can be selected at build time via CMake option `RENDERER_BACKEND=OpenGL`

### 8. FFmpeg Encoder (`render/ffmpeg_encoder.cpp`)

Responsibilities:
- Spawn `ffmpeg` as a child process via pipe
- Accept RGBA frame data, encode to H.264 (opaque) or ProRes 4444 (transparent)
- Mix in the audio WAV from the manifest
- Finalize and close the output file

Encoding parameters:

| Scenario | Codec | Pixel format | Container |
|---|---|---|---|
| Opaque | `libx264` | `yuv420p` | `.mp4` |
| Transparent | `prores_ks -profile:v 4` | `yuva444p10le` | `.mov` |

The output path extension determines container format. If `--transparent` is
active and the output path ends in `.mp4`, warn to stderr and use `.mov`
instead.

Output is written to a temp file (`<output>.tmp`) and renamed to the final path
only after FFmpeg exits 0.

### 9. Logger (`cli/logger.cpp`)

The logger's primary audience is the **director system** (video_agent). The
director spawns this renderer as a subprocess and captures stderr to audit the
render. Warnings are the most important signal: they mean the renderer completed
successfully but made a silent decision that the director did not explicitly
authorise — potential quality issues the director can catch and re-render before
final delivery.

Responsibilities:
- Write structured log lines to stderr (never stdout)
- Stdout is reserved for machine-readable output (none currently, reserved for
  future `--json-status` flag)
- Format: `[LEVEL] <message>`

Log levels: `error`, `warn`, `info`, `debug`

#### Log Level Semantics

**`error`** — fatal; renderer exits non-zero; the director must treat this as a
failed take. Always captured regardless of `--log-level`.

**`warn`** — the render completed and produced output, but the renderer made a
silent corrective decision the director did not request. The director should
inspect warns and decide whether to re-render with a corrected manifest. These
are the primary signal for silent failures.

**`info`** — one line per major pipeline stage. Default level. Gives the
director a human-readable audit trail of what was rendered without flooding
logs.

**`debug`** — per-frame and per-cue detail; high-volume; intended for
renderer development and post-mortem diagnosis of visual anomalies.

#### Director-Facing Warnings (Silent Failures)

These are the situations where the renderer silently adapted rather than
failing, which the director must know about to maintain quality control:

| Trigger | Warning message | Why the director should care |
|---|---|---|
| `--transparent` with `.mp4` output path | `--transparent set but output path ends in ".mp4" — switched container to ".mov"` | Compositing pipeline may expect `.mov`; director should update the manifest |
| Unknown cue key in manifest | `Cue t=2.400s: unknown key "brow_raise" — ignored` | Cue was silently dropped; the intended direction was not applied |
| Empty `lipsync` array | `Lipsync array is empty — mouth will remain closed for the full scene` | Likely a Rhubarb failure upstream; the take will have no lip sync |
| `lipsync` gap > 1.0s between keyframes | `Lipsync gap: no keyframe between t=1.200s and t=2.500s (1.3s) — mouth held at last shape` | Rhubarb may have dropped a segment; visible as frozen mouth |
| Model `id` not in registry | `Model id="hana" not in registry — falling back to path` | Director may have used a stale or misspelled model id |
| Expression name not on model | `Cue t=1.200s: emotion "ecstatic" not defined on model "shiori" — held at current expression` | The intended emotion was silently skipped |
| Motion name not on model | `Cue t=3.500s: reaction "wink" not defined on model "shiori" — skipped` | The intended reaction was silently skipped |
| Audio duration shorter than scene | `Audio ends at t=2.1s but scene is 3.0s — final 0.9s will be silent` | Output video will have a silent tail |
| Audio duration longer than scene | `Audio (4.2s) is longer than scene (3.0s) — audio will be truncated` | Director may have mismatched audio and manifest |
| FFmpeg stderr output | `FFmpeg: "deprecated pixel format used..."` | Passthrough of any FFmpeg warnings for the director to review |

#### Canonical Log Lines by Component

**Startup / manifest (info)**
```
[INFO] live2d-render starting — scene: "scene_01.json"
[INFO] Manifest loaded: schema_version=1.0, model=shiori, fps=30, resolution=1080x1920, frames=90, cues=4, lipsync_keyframes=48
[INFO] Model resolved: id=shiori → "assets/models/shiori/shiori.model3.json"
[INFO] Audio: "results/run_42/audio/scene_01.wav" (3.0s)
[INFO] Output: "results/run_42/avatar_takes/scene_01.mp4" (transparent=false)
```

**Graphics / model init (info)**
```
[INFO] Graphics backend: D3D11 (adapter: "NVIDIA GeForce RTX 4080")
[INFO] Render target: 1080x1920 RGBA, offscreen
[INFO] Live2D model loaded: 42 parameters, 6 expressions, 4 motions, physics enabled
[INFO] FFmpeg encoder started: libx264 yuv420p 30fps → "results/run_42/avatar_takes/scene_01.tmp.mp4"
```

**Render progress (info)**
```
[INFO] Rendering: frame 0/90 (0%)
[INFO] Rendering: frame 30/90 (33%)
[INFO] Rendering: frame 60/90 (67%)
[INFO] Rendering: frame 90/90 (100%)
[INFO] Render complete: 90 frames in 1.24s (72.6 fps)
[INFO] FFmpeg finalized. Output: "results/run_42/avatar_takes/scene_01.mp4" (2.1 MB)
```

Progress lines are emitted at 0%, 33%, 67%, 100% at `info` level. At `debug`
level every frame is logged (see below).

**Cue dispatch (info)**
```
[INFO] Cue t=0.000s: emotion → "neutral"
[INFO] Cue t=1.200s: emotion → "happy"
[INFO] Cue t=3.500s: reaction → "nod"
[INFO] Cue t=6.000s: emotion → "surprised"
```

**Debug — per-frame detail**
```
[DEBUG] Frame 0: t=0.000s mouth=(open=0.0 form=0.0 shape=X) emotion=neutral gaze=(0.0,0.0) head=(yaw=0 pitch=0 roll=0)
[DEBUG] Frame 1: t=0.033s mouth=(open=0.3 form=0.0 shape=D) emotion=neutral gaze=(0.0,0.0) head=(yaw=0 pitch=0 roll=0)
[DEBUG] Frame 36: t=1.200s cue dispatched emotion="happy" blend_start
[DEBUG] Frame 36: t=1.200s mouth=(open=0.8 form=0.0 shape=B) emotion=happy[blending 0ms/300ms] gaze=(0.0,0.0) head=(yaw=0 pitch=0 roll=0)
```

**Debug — init detail**
```
[DEBUG] Registry loaded: 3 entries (shiori, hana, kei)
[DEBUG] Manifest field "extra_metadata" unrecognized — ignored
[DEBUG] D3D11 device created: feature level 11.1
[DEBUG] Offscreen framebuffer allocated: 1080x1920x4 = 8.3 MB
[DEBUG] FFmpeg command: ffmpeg -f rawvideo -pix_fmt rgba -s 1080x1920 -r 30 -i pipe:0 -i "scene_01.wav" -c:v libx264 -pix_fmt yuv420p "scene_01.tmp.mp4"
```

#### Format Details

```
[LEVEL] <message>
```

- `LEVEL` is left-padded to 5 chars: `ERROR`, `WARN `, `INFO `, `DEBUG`
- No timestamp by default; add `--log-timestamps` to prefix each line with
  `HH:MM:SS.mmm` (useful when redirecting stderr to a log file)
- All lines end with `\n`; no color codes (stderr may be a pipe)

The director system should treat any `WARN ` line on stderr as a signal to
inspect the take before accepting it. A render with warnings exits 0, but the
output may not match the intended direction.

---

## Data Flow

```
scene manifest JSON
      │
      ▼
 ManifestLoader ──────────────────────────────────────────┐
      │                                                    │
      │ SceneManifest                                      │
      ├──────────────────┬──────────────────┐             │
      ▼                  ▼                  ▼             │
 ModelResolver    LipsyncSequencer    CueSequencer        │
      │                  │                  │             │
      ▼                  └──────────────────┘             │
 Cubism Engine                 │ per-frame state          │
      │                        ▼                          │
      └──────────► RenderLoop ◄────────────────────────── ┘
                       │
                       ▼
               OffscreenRenderer
                       │  RGBA frames
                       ▼
               FFmpegEncoder ◄── audio WAV
                       │
                       ▼
                  output.mp4
```

---

## File Structure

```
src/
├── main.cpp                        # Entry point; wires all components
├── cli/
│   ├── args.cpp / args.h           # Argument parsing
│   ├── manifest.cpp / manifest.h   # Manifest load, validate, override
│   ├── model_resolver.cpp / .h     # Registry lookup + path fallback
│   └── logger.cpp / logger.h       # Stderr logging
└── render/
    ├── render_loop.cpp / .h        # Frame loop orchestrator
    ├── lipsync_sequencer.cpp / .h  # Rhubarb keyframe → mouth params
    ├── cue_sequencer.cpp / .h      # Director cue dispatch
    ├── offscreen_d3d11.cpp / .h    # D3D11 headless render target
    ├── offscreen_opengl.cpp / .h   # OpenGL headless render target
    └── ffmpeg_encoder.cpp / .h     # FFmpeg child-process encoder
```

---

## Error Handling Policy

- All errors are logged to stderr before exit
- Error messages include the field name and value that caused the failure
- The renderer never silently swallows errors or produces a partial output
- Unknown/unrecognized fields are ignored (not errors) per the contract's
  forward-compatibility rules
- The only exception: unrecognized `schema_version` is a hard error (exit 2)

Example error messages:

```
[ERROR] Manifest validation failed: missing required field "audio"
[ERROR] Model not found: id="shiori" not in registry, path="assets/models/shiori/shiori.model3.json" does not exist
[ERROR] Audio file not found: "results/run_42/audio/scene_01.wav"
[ERROR] Unrecognized schema_version "2.0" — supported versions: ["1.0"]
```

---

## Build Configuration

CMake options:

| Option | Default | Description |
|---|---|---|
| `RENDERER_BACKEND` | `D3D11` | Graphics backend: `D3D11` or `OpenGL` |
| `FFMPEG_PATH` | (system PATH) | Explicit path to `ffmpeg` binary |
| `ASSETS_DIR` | `assets/` | Root for model registry and model files |

---

## Non-Goals

The CLI does **not**:
- Run interactively or accept stdin
- Stream frames over a network
- Analyze audio or run Rhubarb
- Make any LLM calls or creative decisions
- Expose a server or daemon mode
