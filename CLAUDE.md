# Claude Code Configuration

## Permissions

Claude has full permissions for this directory. Proceed autonomously without asking for confirmation on:
- Reading, editing, creating, and deleting files
- Running build commands, scripts, and tests
- Installing dependencies
- Any git operations within this repository

## Project Overview

**Live2D Avatar Renderer** — A CLI/embeddable function that accepts a scene manifest from an orchestrating system and renders a Live2D avatar to video.

### Mental Model

This project is an **actor**, not a director. The external orchestrator (video_agent) provides the script, audio, emotional cues, and timing. This system interprets those directions and renders the performance to video.

### Inputs

A **scene manifest** (JSON) with:
- `model` — path to `.model3.json`
- `audio` — voice-over WAV for lip sync
- `output` — destination video file
- `resolution`, `fps`
- `cues` — timed directives (emotions, reactions, gaze, head angles)

### Outputs

Rendered video with lip sync, expression changes, reactions, physics simulation, and optional transparent background.

### Architecture

```
[Director System] → scene manifest (JSON)
      ↓
Renderer CLI
  ├── Audio Analyzer  → Live2D Model Engine (Cubism Native SDK 5-r.4.1)
  └── Cue Sequencer   →        ↓
                       Offscreen Renderer (D3D11 / OpenGL)
                               ↓
                       Video Encoder (FFmpeg)
      ↓
output.mp4
```

### Development Stack

| Component | Technology |
|---|---|
| Model rendering | Live2D Cubism Native SDK 5-r.4.1 |
| Graphics backend | D3D11 (Windows primary), OpenGL (cross-platform) |
| Lip sync | Audio amplitude → `ParamMouthOpenY` |
| Video encoding | FFmpeg |
| Build system | CMake + Visual Studio 2022 |

### Directory Structure

```
cubism/
├── Core/         # Live2D Cubism Core library (prebuilt binaries)
├── Framework/    # Source code for rendering and animation (submodule)
└── Samples/
    ├── D3D9/     # DirectX 9.0c sample
    ├── D3D11/    # DirectX 11 sample
    ├── Metal/    # Metal sample (macOS/iOS)
    ├── OpenGL/   # OpenGL sample
    ├── Vulkan/   # Vulkan sample
    └── Resources/# Model files and assets
docs/
└── live2d-avatar-api-contract.md  # Full interface contract
```

### Key Files

- `docs/live2d-avatar-api-contract.md` — scene manifest schema, cue vocabulary, CLI spec
- `docs/authoring-guide.md` — **read this before working on any motion or expression**. Two-part document: (1) quick-reference format specs — motion vs expression classification, `.motion3.json` and `.exp3.json` formats, registry entry syntax, entry validation modes (none/implicit/explicit), normalisation behaviour (smoothstep, auto-rate, 0.1s minimum), breath guard modes, breath speed, and common failure modes; (2) step-by-step authoring workflow — audit → author → review render → human review → revision loop → registry update → spec compliance, plus accumulated lessons from the majo reference implementation (axis calibration, FadeOut residual snap, review overlay standards, and more).
- `docs/motion-definition.md` — detailed spec for motion entry classification and out-of-range handling (the authoritative reference; `authoring-guide.md` is the fast-lookup summary)
- `docs/model-onboarding.md` — checklist for evaluating and registering new models (pass/fail criteria, test-render workflow, rejection log)
- `assets/models/registry.json` — model registry mapping IDs to paths, emotions, and reactions
- `SDK_README.md` — Live2D Cubism SDK reference (internal rendering layer)
- `Framework/` — Cubism Native Framework (rendering, animation, model loading)
- `Samples/D3D11/Demo/proj.*/` — D3D11 sample projects

### Development Environment (Windows)

- Visual Studio 2022 (17.14.2)
- CMake 3.31.7
- Target: Windows 10/11

## Renderer Binary — Auto-Build Guard

Before running any command that invokes the renderer, resolve the binary path as follows:

1. **Read `.env`** (project root). If it exists, load `LIVE2D_RENDER_BIN` from it.
2. **Fall back to platform defaults** if `.env` is absent or the variable is unset:
   - Linux: `build/live2d-render`
   - Windows: `build/Release/live2d-render.exe`
3. **Check that the binary exists** (`test -f "$LIVE2D_RENDER_BIN"`).
4. **If it does not exist, build it automatically:**
   ```bash
   # Linux
   cmake --preset linux && cmake --build --preset linux
   # Windows
   cmake --preset windows && cmake --build --preset windows
   ```
5. After a successful build, **create or update `.env`** with the resolved path:
   ```
   LIVE2D_RENDER_BIN=build/live2d-render   # adjust for Windows
   ```
6. Then proceed with the original task.

Never ask the user to build manually unless the build itself fails. The build is fast and idempotent — prefer doing it over blocking.

## Review Artifacts — Output Convention

Human-reviewable output (MP4 comparisons, annotated renders, review clips) must be written to **`results/tests/<feature-name>/`** inside the repo, never to `/tmp` or other ephemeral paths. The `results/` tree is gitignored, so outputs are persistent within the workspace but not committed.

- Review render scripts (`render_review.py` and equivalents) must resolve their output directory as `<repo_root>/results/tests/<feature>/`.
- Intermediate/scratch files (un-annotated raw renders) go to `results/tests/<feature>/_tmp/` and are also gitignored.
- Final deliverable for human review is the concatenated annotated MP4 at `results/tests/<feature>/review_<feature>.mp4`.
- Every clip must be **at least 5 seconds long** and must include a **5-second idle buffer after the last meaningful action** so the reviewer can see the full recovery. Achieve this by adding a sentinel `{"time": T, "emotion": "neutral"}` cue at whatever time T gives `T + 1.0s render_loop_tail ≥ max(5.0, last_action_end + 5.0)`.

The same convention applies to the `breath_guard_review` script — if re-run, its output should be redirected to `results/tests/breath_guard_review/`.
