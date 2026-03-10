# Live2D Avatar API Contract

**Version:** 1.0
**Producer:** video_agent (AvatarCueAgent)
**Consumer:** this renderer

---

## Overview

This renderer is a pure render actor. The upstream video_agent system is
responsible for all scripting, audio generation, lipsync analysis, and cue
generation. This renderer's only responsibility is to accept a fully-specified
scene manifest and produce a video file.

---

## Division of Responsibility

| Concern | Owner |
|---|---|
| Script and dialogue | video_agent (ScriptAgent) |
| TTS audio generation | video_agent (AudioAgent / ElevenLabs) |
| Rhubarb lipsync analysis | video_agent (AvatarCueAgent) |
| Emotion and reaction cue generation | video_agent (AvatarCueAgent, LLM-driven from script) |
| Avatar rendering | this renderer |
| Final compositing (avatar over background) | video_agent (FFmpeg) |

This renderer does **not** analyze audio, run Rhubarb, call any LLM, or make
any creative decisions.

---

## Scene Manifest

File: `AvatarSceneManifest.json`
Written by: video_agent AvatarCueAgent
Read by: this renderer's CLI

```json
{
  "schema_version": "1.0",
  "model": {
    "id": "shiori",
    "path": "assets/models/shiori/shiori.model3.json"
  },
  "audio": "results/<run_id>/audio_segments/scene_01.wav",
  "output": "results/<run_id>/avatar_takes/scene_01.mp4",
  "resolution": [1080, 1920],
  "fps": 30,
  "background": "transparent",
  "lipsync": [
    { "time": 0.00, "mouth_shape": "X" },
    { "time": 0.04, "mouth_shape": "A" },
    { "time": 0.12, "mouth_shape": "B" },
    { "time": 0.20, "mouth_shape": "C" }
  ],
  "cues": [
    { "time": 0.0,  "emotion": "neutral" },
    { "time": 1.2,  "emotion": "happy" },
    { "time": 3.5,  "reaction": "nod" },
    { "time": 6.0,  "emotion": "surprised" }
  ]
}
```

### Top-level fields

| Field | Type | Description |
|---|---|---|
| `schema_version` | string | Contract version; reject manifests with an unrecognized version |
| `model` | object | Model selection; see below |
| `audio` | string | WAV voiceover file; mixed into output audio track; not analyzed for lipsync |
| `output` | string | Destination MP4 path |
| `resolution` | [int, int] | `[width, height]` in pixels |
| `fps` | int | Target frame rate |
| `background` | string | `"transparent"` for alpha output, hex color `"#1a1a2e"`, or path to background image |
| `lipsync` | array | Dense phoneme keyframe timeline; see below |
| `cues` | array | Sparse director cues; see below |

### Model object

video_agent specifies which Live2D character model to render. Resolve `id`
against the local model registry (`assets/models/registry.json`). If `id` is
not found in the registry, fall back to `path`. If neither resolves, exit
non-zero with a clear error message.

```json
"model": {
  "id": "shiori",
  "path": "assets/models/shiori/shiori.model3.json"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Logical model identifier; must match an entry in `assets/models/registry.json` |
| `path` | string | no | Explicit filesystem path to `.model3.json`; fallback if `id` is unregistered |

### Model Registry

The model registry is maintained in `assets/models/registry.json`. Each entry
maps a logical `id` to a model path and declares the expressions and motions
available on that model.

```json
[
  {
    "id": "shiori",
    "path": "assets/models/shiori/shiori.model3.json",
    "expressions": ["neutral", "happy", "sad", "surprised", "angry"],
    "motions": ["nod", "shake", "look_away", "blink"]
  }
]
```

video_agent reads this file at pipeline start to validate model IDs and
available expressions before generating manifests.

---

## Lipsync Array

`lipsync` is a dense keyframe timeline pre-computed by video_agent using
[Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync). The
renderer reads it as a direct keyframe table and maps each shape code to the
corresponding Live2D mouth parameters. No audio analysis is performed here.

Entries are sorted ascending by `time`. Interpolate between adjacent entries
each frame.

```json
{ "time": 0.04, "mouth_shape": "A" }
```

| Field | Type | Description |
|---|---|---|
| `time` | float | Seconds from scene start |
| `mouth_shape` | string | One of the 9 Rhubarb shape codes (see table below) |

### Rhubarb Mouth Shape Vocabulary

All 9 codes must be mapped to Live2D parameter values. There is no fallback to
amplitude-based lipsync.

| Code | Phoneme group | Description |
|---|---|---|
| `X` | silence | Mouth closed / rest position |
| `A` | m, b, p | Lips pressed together |
| `B` | aa, ae, ah | Mouth open wide |
| `C` | ao, aw, er | Rounded open |
| `D` | ih, iy, eh, ey | Slight open |
| `E` | oh | Rounded mid |
| `F` | f, v | Top teeth on lower lip |
| `G` | l, n, th | Tongue near teeth |
| `H` | y, r | Slight open / rounded |

---

## Cues Array

`cues` is a sparse timeline of director instructions. Apply each cue at its
timestamp by blending to the target expression or triggering the named motion
clip. Unknown cue keys must be ignored (forward compatibility).

```json
{ "time": 1.2, "emotion": "happy" }
{ "time": 3.5, "reaction": "nod" }
{ "time": 4.1, "gaze": { "x": 0.5, "y": -0.2 } }
{ "time": 5.0, "head":  { "yaw": 10, "pitch": -5, "roll": 0 } }
```

### Supported cue types

| Key | Value type | Description |
|---|---|---|
| `emotion` | string | Blend to named facial expression: `"neutral"`, `"happy"`, `"sad"`, `"surprised"`, `"angry"` |
| `reaction` | string | Trigger a pre-built motion clip: `"nod"`, `"shake"`, `"look_away"`, `"blink"` |
| `gaze` | `{ "x": float, "y": float }` | Eye direction override; range -1.0 to 1.0 on each axis |
| `head` | `{ "yaw": float, "pitch": float, "roll": float }` | Head angle override in degrees |

Each cue object contains exactly one directive key plus `time`.

---

## CLI

```bash
# Render a single scene take
live2d-render --scene scene_01.json

# Override output path
live2d-render --scene scene_01.json --output take_02.mp4

# Transparent background for compositing (recommended for video_agent pipeline)
live2d-render --scene scene_01.json --transparent
```

Exit 0 on success. Exit non-zero on any failure (bad manifest, missing model,
missing audio, render error). Write the output MP4 to the path in the manifest
(or `--output` override) only on success.

---

## Schema Evolution Rules

- Increment `schema_version` on any breaking change.
- Additive changes (new optional cue types, new optional top-level fields) do
  not require a version bump provided the renderer ignores unknown keys.
- Reject manifests with an unrecognized `schema_version` and exit non-zero.
