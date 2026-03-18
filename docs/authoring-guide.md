# Live2D Authoring Guide

**Audience:** Claude sessions authoring, registering, or debugging motions and expressions for this renderer.
**Scope:** Authoring decisions, file formats, registry entries, entry validation, normalisation, and breath guard. C++ internals are omitted unless they affect authoring choices.

---

## 1. Core Concepts

Motions drive physical movement (head angles, gaze, body); their visual correctness depends on the model's parameter state at the moment they start. Expressions drive emotional state (eye shape, brow, mouth curve); they must not rely on a specific head angle or body position, but facial element parameters (eyes, brows, mouth) are permitted — these produce a recognisable result regardless of starting pose. The hard decision rule: if the semantic is *movement*, it is a motion; if the semantic is *emotional state*, it is an expression.

---

## 2. Motion Authoring Quick-Reference

### File format

A `.motion3.json` file has three top-level keys: `Version`, `Meta`, and `Curves`.

```json
{
  "Version": 3,
  "Meta": {
    "Duration": 1.5,
    "Fps": 30.0,
    "Loop": false,
    "AreBeziersRestricted": true,
    "CurveCount": 1,
    "TotalSegmentCount": 5,
    "TotalPointCount": 6,
    "UserDataCount": 0,
    "TotalUserDataSize": 0
  },
  "Curves": [
    {
      "Target": "Parameter",
      "Id": "ParamAngleY",
      "FadeInTime": 0.1,
      "FadeOutTime": 0.6,
      "Segments": [
        0.0, 0.0,
        0, 0.35, -22.0,
        0, 0.65, 2.0,
        0, 0.9, -8.0,
        0, 1.2, 0.0,
        0, 1.5, 0.0
      ]
    }
  ],
  "UserData": []
}
```

This is the actual `majo/motions/nod.motion3.json` file.

### Segments array encoding

The `Segments` array encodes the entire curve as a flat list. The first two values are always the initial anchor point `[t0, v0]`. After that, each segment is encoded as:

```
seg_type, ...args, t_end, v_end
```

Two segment types are supported:

| Type | Code | Extra args | Description |
|---|---|---|---|
| LINEAR | `0` | none | Straight line from previous point to `(t_end, v_end)` |
| BEZIER | `1` | 4 floats: `cx1, cy1, cx2, cy2` | Cubic bezier; control points relative to segment endpoints |

**LINEAR example (from nod.motion3.json):**
```
0.0, 0.0,        ← initial anchor at t=0.0, value=0.0
0, 0.35, -22.0,  ← LINEAR segment: type=0, end=(t=0.35, v=-22.0)
0, 0.65, 2.0,    ← LINEAR segment: end=(t=0.65, v=2.0)
...
```

### Meta field counting rules

These counts must be exact or the SDK will reject the file.

| Field | Rule |
|---|---|
| `CurveCount` | Total number of objects in the `Curves` array |
| `TotalSegmentCount` | Sum of segments across all curves. Each `LINEAR` or `BEZIER` entry after the initial anchor counts as one segment. For nod.motion3.json: 5 segments in the one curve → `TotalSegmentCount: 5` |
| `TotalPointCount` | Number of (time, value) pairs across all curves. For LINEAR: initial anchor + 1 point per segment endpoint. For BEZIER: initial anchor + 3 points per segment (2 control points + 1 endpoint). For nod.motion3.json: 1 anchor + 5 LINEAR endpoints = 6 → `TotalPointCount: 6` |

### Registering the motion in model3.json

The motion group name in `FileReferences.Motions` must match the `id` used in the registry entry. The renderer looks up motion files through the model3.json `Motions` section — if the group is missing there, the motion will silently never fire.

---

## 3. Expression Authoring Quick-Reference

### File format

```json
{
  "Type": "Live2D Expression",
  "Version": 3,
  "Parameters": [
    { "Id": "ParamBrowLY",   "Value": 0.8,  "Blend": "Add" },
    { "Id": "ParamMouthForm","Value": 0.9,  "Blend": "Add" },
    { "Id": "ParamEyeLOpen", "Value": 1.0,  "Blend": "Multiply" },
    { "Id": "ParamEyeROpen", "Value": 1.0,  "Blend": "Multiply" }
  ]
}
```

### Rules

- Expressions must not rely on a specific head angle or body position. Movements of facial elements (eyes, brows, mouth) are permitted — these read correctly from any starting pose.
- Only use `Multiply` or `Add` blend modes. `Multiply` is appropriate for eye openness (scales the current value); `Add` is appropriate for brow height and mouth curve (offsets from the current value).
- Every registered expression must produce a **visually distinct, recognisable facial state** that a human reviewer can label with a single semantic term from the approved vocabulary: `neutral`, `curious`, `angry`, `sad`, `happy`, `surprised`, `embarrassed`, `bored` (universal vocabulary — not every emotion is required or approved per model; each model registers only the subset that reads as visually distinct on its rig).
- The minimum viable emotional vocabulary is: `neutral` + at least two distinct non-neutral emotions.
- The majo expressions (in `assets/models/majo/expressions/`) are the known-good reference set for this renderer: 8 `.exp3.json` files exist on disk, but only 6 are registered (`neutral`, `happy`, `surprised`, `bored`, `sad`, `angry`). The files `curious.exp3.json` and `embarrassed.exp3.json` remain on disk but were dropped from the registry after human review as indistinct on this rig.

---

## 4. Registry Entry Format

`assets/models/registry.json` is a JSON array. Each entry maps a model ID to its file path, expressions, and reactions.

### Entry-independent reaction (no valid_entry)

```json
{
  "id": "majo",
  "path": "assets/models/majo/majo.model3.json",
  "emotions": {
    "neutral": {
      "id": "neutral",
      "note": "Slight upward mouth curve. Calm resting state."
    },
    "happy": {
      "id": "happy",
      "note": "Eyes closed to smile shape with raised brows. Warm, positive."
    }
  },
  "reactions": {
    "idle": {
      "id": "Idle",
      "note": "Default idle loop."
    }
  }
}
```

Fields:
- `id` — lowercase ASCII; used in scene manifest `model` field and all logging.
- `path` — relative to the live2d repo root; must point to the `.model3.json` file.
- `emotions.<label>.id` — the expression ID as it appears in `FileReferences.Expressions` of the model3.json.
- `reactions.<label>.id` — the motion group name as it appears in `FileReferences.Motions` of the model3.json.
- `note` — human-readable description; required for onboarded models, optional for review entries.

### Entry-dependent reaction (with valid_entry)

```json
"nod": {
  "id": "Nod",
  "note": "Forward head dip. Entry-dependent: assumes head near yaw center.",
  "entry": "dependent",
  "valid_entry": {
    "ParamAngleX": { "min": -5, "max": 5 }
  },
  "out_of_range_mode": "implicit",
  "normalise_rate": 0
}
```

Additional fields:
- `entry` — `"independent"` or `"dependent"`. Independent reactions omit `valid_entry`.
- `valid_entry` — map of parameter ID to `{ "min": float, "max": float }` in the model's native units. Any parameter not listed is unconstrained.
- `out_of_range_mode` — `"none"`, `"implicit"`, or `"explicit"`. Default is `"implicit"` if omitted. Use `implicit` for all production entries; `explicit` is not recommended (halts rendering on violation rather than normalising through).
- `normalise_rate` — float (units/second) or `0`. Value `0` means auto-compute from breath speed. **Omit this field or set to `0` in all normal cases.** Only override to force unusually slow or fast centering.

---

## 5. Entry Validation Decision Tree

Three modes control what happens when a motion is triggered with out-of-range parameters:

```
Is this motion entry-dependent?
├── No  → set entry: "independent", omit valid_entry. Done.
└── Yes → declare valid_entry bounds. Then:
    │
    └── Who consumes the renderer output?
        ├── Runtime rendering / real-time playback, or scripted pipeline agent
        │   → use out_of_range_mode: "implicit"
        │   Renderer auto-inserts normalisation; timing extends silently.
        │   Prefer this for all production registrations — renders the full
        │   sequence with warnings rather than halting on entry violations.
        │
        └── Review renders / debugging uncorrected behaviour
            → use out_of_range_mode: "none"
            No check is performed; motion plays immediately from any state.
            Use only in review registry entries (e.g. majo_nod_nocheck).
```

**Rule:** Use `implicit` for all production registrations — both runtime and scripted pipeline. The renderer inserts normalisation and logs a warning; the sequence completes without interruption. Use `none` only in explicitly labelled review entries.

---

## 6. Normalisation Behaviour

When `out_of_range_mode` is `implicit` and parameters are out of range, the renderer auto-inserts a normalisation motion before the requested clip.

**Movement shape:** smoothstep ease-in/ease-out: `f(t) = t²(3 − 2t)`. Velocity is zero at both endpoints. The head accelerates into the move and decelerates to the boundary. This reads as deliberate and volitional — not mechanical.

**Auto-rate formula:** `normalise_rate = 2 × amplitude × weight × 2π / period` for the constrained parameter. On majo's `ParamAngleX` (amplitude=15, weight=0.5, period=6.5345s): auto rate ≈ 14.4 units/s. The head moves at approximately twice the natural idle breath speed.

**Minimum duration:** 0.1 seconds, even for sub-1-unit violations. This ensures the ease-in/ease-out curve is perceptible rather than resolving in a single frame.

**Duration determination:** the worst-case (largest) violation across all constrained parameters sets the duration.

**Warning log format:**
```
WARN [motion] nod: entry out of range — ParamAngleX=7.0(valid:-5.0..5.0)
     | normalise_rate=14.4 units/s normalisation_duration=0.139s
     | actual_clip_start=t=2.139 (requested t=2.000)
     | to hit t=2.000 trigger normalisation at t=1.861
```

**Human-observable consequence:** before the motion plays, the head moves at roughly twice the natural idle oscillation speed, with eased start and stop, from its current position to the valid entry boundary. The full sequence seen by a reviewer is: idle breathing → ease-in/out centering → requested motion → breath guard fade-out → idle resumes.

**Breath guard interaction:** normalisation activates the breath guard at the start of the normalisation motion, not at the start of the requested clip. The guard covers the entire normalise-then-play sequence.

**Overlap with concurrent motions:** normalisation is applied as a parameter-level pass *after* the Cubism motion manager runs each frame (`SetParameterValue` called on the target params after `UpdateMotion`). This means normalisation always wins on its target parameters — a currently-playing motion continues but its contribution to those params is overridden for the duration of the normalisation. The pending reaction is not queued until normalisation completes; if another motion is still active at that point, the reaction waits in the Cubism queue and starts when that motion finishes.

---

## 7. Breath Guard

The breath guard controls whether and how `CubismBreath` oscillation is suppressed while a priority-2 reaction motion is active.

| Mode | Behaviour | Visual quality |
|---|---|---|
| No guard | Breath runs continuously through all motions | Most natural for short reactions; exit is seamless because breath was never suppressed |
| Binary guard | Breath fully suppressed; resumes instantly at motion end | Visible snap on exit; accumulated phase can jump ±15° in one frame. **Do not use.** |
| Lerp guard | Breath suppressed during reaction; fades back in over 0.5s after motion ends | Prevents snap for long reactions; adds a brief "return to centre → fade in" beat that is perceptible on short reactions |

**Current implementation:** lerp guard is active and is the production implementation in `src/render/live2d_model.cpp`.

**Decision rule:** use lerp guard for reactions longer than ~1.5s; no guard for short reactions (nod, tap). The recommended next step is a per-reaction guard mode property or a duration-based heuristic (`duration > 1.5s → lerp guard`).

**Normalisation interaction:** the breath guard activates at normalisation start. The guard covers the entire normalise-then-play sequence. Explicit mode errors fire before any guard state is modified — no side effects.

---

## 8. Breath Speed

`breath_speed` is a float multiplier in the scene manifest (default `1.0`). It scales the breath oscillation rate globally for the scene.

**Naturalness finding:** values up to 3× have been reviewed on tested models (including majo) and rated as human-perceivable as natural breathing variation. Values above 3× have not been validated.

**Auto normalise rate:** the auto normalise rate is computed from the **base** breath parameters (before any `breath_speed` scaling). Changing `breath_speed` in the manifest does **not** adjust the auto normalise rate — they are independent. If a scene uses a non-default `breath_speed` and a reaction fires near a breath peak, the normalisation distance will differ from the 1× expectation but the rate stays fixed at the base-computed value.

---

## 9. Common Failure Modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Nod fires but head is already tilted at motion start | Entry check disabled (`none` mode) or `entry` not declared as `dependent` | Set `entry: "dependent"`, declare `valid_entry` bounds, set `out_of_range_mode: "implicit"` |
| Normalisation looks like a snap or lurch | Duration too short, or constant-velocity implementation | Smoothstep is the correct implementation; verify the 0.1s minimum is enforced; if still snappy, the normalise_rate may be too high — lower it or set to 0 for auto |
| Nod never fires | Motion group missing from model3.json, or `.motion3.json` file does not exist on disk | Check `FileReferences.Motions` in model3.json for the group name; verify the file path resolves from the repo root |
| Head snaps sideways when a long reaction exits | Lerp guard not active; binary guard or no-guard used for a reaction > ~1.5s | Enable lerp guard mode for the reaction; confirm the `fix/breath-snap-renderer` implementation is in use |
| Expression produces no visible change | Parameters authored but wrong blend mode, or parameter IDs do not match this model's cdi3.json | Open the `.cdi3.json`, verify parameter IDs exist; check blend modes (`Multiply` for openness, `Add` for offsets) |
| Two expressions look identical after onboarding | Parameter values too similar or same parameters used with similar magnitudes | Widen the delta on a distinguishing parameter, or drop one expression from the registered set |

---

## 10. Manifest breath_speed Field

The `breath_speed` field in the scene manifest is intended for calibration and review renders where naturalness at non-default oscillation rates needs to be evaluated. Use it when producing review clips that test a model's readability at accelerated or slowed idle breathing, or when a specific scene's pacing has been intentionally authored to require a different breath rate.

**Do not override `breath_speed` in production scene manifests** unless the scene has been explicitly authored and human-reviewed at that speed. The default value of `1.0` is calibrated to read as natural across all validated models. Non-default values also shift the auto normalise rate, which can make normalisation motions faster or slower than expected — a change that may not be noticed until a reaction fires near a breath peak.
