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
- `docs/model-onboarding.md` — checklist for evaluating and registering new models (pass/fail criteria, test-render workflow, rejection log)
- `assets/models/registry.json` — model registry mapping IDs to paths, emotions, and reactions
- `SDK_README.md` — Live2D Cubism SDK reference (internal rendering layer)
- `Framework/` — Cubism Native Framework (rendering, animation, model loading)
- `Samples/D3D11/Demo/proj.*/` — D3D11 sample projects

### Development Environment (Windows)

- Visual Studio 2022 (17.14.2)
- CMake 3.31.7
- Target: Windows 10/11
