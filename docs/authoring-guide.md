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

## 8. Fade-to-Idle and Motion FadeOut Interaction

`fade_to_idle: true` in the registry entry causes the renderer to run a post-motion blend: it captures a snapshot of the model's final parameter state, then linearly lerps from that snapshot toward the current breath-driven output over `fade_to_idle_duration` seconds. This smooths the return to idle breathing without a discontinuity at motion end.

### The FadeOut blending residual

When a motion's per-curve `FadeOutTime > 0`, the Cubism SDK applies an ease-in-out fade weight that drops from 1.0 to 0.0 over the last `FadeOutTime` seconds. The blending formula each frame is:

```
saved_state = fadeWeight × motionValue + (1 − fadeWeight) × saved_state_prev
```

The fixed point of this recurrence is `saved_state = motionValue` (not 0). Because `motionValue` also approaches 0 near the motion's end, the saved state converges toward 0 — but slowly. By the time the motion ends and the ease-in-out FadeOut weight reaches 0, the saved state has **not** reached 0. It is frozen at whatever value the blending dynamics accumulated.

**Concrete example (look_away, FadeOut=1.0, curve returning AngleX 20° → 0° over t=1.0–2.0):**
- At t=2.0 (motion end): `_savedParameters.angleX ≈ 6.07°`
- Rate of change at motion end: ≈ −0.45°/s (nearly frozen)
- Lerp's initial rate (duration=1.0s): −6.07°/s
- Velocity jump at the look_away → fade_to_idle transition: **13×** — visible snap/lurch

### Fix: set FadeOutTime=0.0 for motions that return to 0 via their curve

When a motion's keyframe curve explicitly returns every driven parameter to its default value (typically 0) before the motion ends, the SDK override at full weight (`fadeWeight = 1.0`) writes the terminal 0 cleanly into `_savedParameters`. No residual.

**Rule:** Set `"FadeOutTime": 0.0` on each motion curve that:
1. explicitly returns to 0° (or its parameter default) by the motion's end time, **and**
2. the reaction is registered with `fade_to_idle: true`.

With `FadeOutTime=0`, `fout = 1.0` throughout. At motion end the saved state = `motionValue` = 0. Snapshot = 0. Lerp starts at 0° → converges to 0° + breath. No velocity discontinuity.

**When to keep FadeOutTime > 0:** leave it non-zero only when:
- The motion does NOT return to neutral via its own curve (e.g. an abrupt-end hold that relies on FadeOut to blend out), or
- The motion may be forcibly interrupted by a higher-priority motion and needs a FadeOut for that cross-fade. Since interrupting reactions is uncommon in this pipeline, `FadeOutTime=0` is safe for most `fade_to_idle` reactions.

### Flush at arm time

The renderer also calls `SaveParameters()` with gaze-neutral values at the moment fade_to_idle is armed. This flush zeroes any remaining residual in `_savedParameters` so that subsequent `LoadParameters()` calls during the lerp restore a clean base (0° + gradually-reintroduced breath), not the motion's accumulated blending history.

The two fixes are complementary:
- `FadeOutTime=0` prevents the residual from building up in the first place (motion-side fix).
- The flush at arm time eliminates any residual that slipped through, e.g. from an interrupted or specially-structured motion (renderer-side fix).

---

## 9. Breath Speed

`breath_speed` is a float multiplier in the scene manifest (default `1.0`). It scales the breath oscillation rate globally for the scene.

**Naturalness finding:** values up to 3× have been reviewed on tested models (including majo) and rated as human-perceivable as natural breathing variation. Values above 3× have not been validated.

**Auto normalise rate:** the auto normalise rate is computed from the **base** breath parameters (before any `breath_speed` scaling). Changing `breath_speed` in the manifest does **not** adjust the auto normalise rate — they are independent. If a scene uses a non-default `breath_speed` and a reaction fires near a breath peak, the normalisation distance will differ from the 1× expectation but the rate stays fixed at the base-computed value.

---

## 10. Common Failure Modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Nod fires but head is already tilted at motion start | Entry check disabled (`none` mode) or `entry` not declared as `dependent` | Set `entry: "dependent"`, declare `valid_entry` bounds, set `out_of_range_mode: "implicit"` |
| Normalisation looks like a snap or lurch | Duration too short, or constant-velocity implementation | Smoothstep is the correct implementation; verify the 0.1s minimum is enforced; if still snappy, the normalise_rate may be too high — lower it or set to 0 for auto |
| Nod never fires | Motion group missing from model3.json, or `.motion3.json` file does not exist on disk | Check `FileReferences.Motions` in model3.json for the group name; verify the file path resolves from the repo root |
| Head snaps sideways when a long reaction exits (breath phase snap) | Lerp guard not active; binary guard or no-guard used for a reaction > ~1.5s | Enable lerp guard mode for the reaction |
| Head snaps or lurches at the **start** of fade_to_idle | Motion's per-curve `FadeOutTime > 0` leaves a blending residual (~6°) in `_savedParameters`; the lerp's initial velocity is much higher than the motion's near-zero exit velocity | Set `"FadeOutTime": 0.0` on each curve that explicitly returns to 0 via its keyframe data (see §8) |
| Body snap after face snap is resolved at fade_to_idle end | `BodyAngleX` not included in the `SaveParameters` flush at arm time | C++ renderer issue; confirmed fixed — `_idParamBodyAngleX` is written to 0 before the flush |
| Expression produces no visible change | Parameters authored but wrong blend mode, or parameter IDs do not match this model's cdi3.json | Open the `.cdi3.json`, verify parameter IDs exist; check blend modes (`Multiply` for openness, `Add` for offsets) |
| Two expressions look identical after onboarding | Parameter values too similar or same parameters used with similar magnitudes | Widen the delta on a distinguishing parameter, or drop one expression from the registered set |

---

## 11. Manifest breath_speed Field

The `breath_speed` field in the scene manifest is intended for calibration and review renders where naturalness at non-default oscillation rates needs to be evaluated. Use it when producing review clips that test a model's readability at accelerated or slowed idle breathing, or when a specific scene's pacing has been intentionally authored to require a different breath rate.

**Do not override `breath_speed` in production scene manifests** unless the scene has been explicitly authored and human-reviewed at that speed. The default value of `1.0` is calibrated to read as natural across all validated models. Non-default values also shift the auto normalise rate, which can make normalisation motions faster or slower than expected — a change that may not be noticed until a reaction fires near a breath peak.

---

---

# Authoring Workflow

**Status:** Draft — pending D2 sign-off
**Spec version:** 1.0 (2026-03-17)
**Reference implementation:** majo (completed 2026-03-18)

---

## Purpose

This section is the step-by-step guide for authoring Layer 2 behaviours for any new Live2D model. Follow it whenever a model needs motion clips or expression files built from scratch — typically any VTubeStudio-origin model that has no existing authoring.

The workflow is a cycle: **agent proposes → renders review video → human reviews → agent refines → repeat.** It runs from initial prerequisites through spec compliance sign-off.

For the registry entry format, motion file format, expression file format, and breath guard configuration, see sections 1–11 above. This section covers *process*; the sections above cover *format*.

---

## Background: What you do and do not need to author

The renderer already provides several behaviours unconditionally for any correctly configured model. Do not attempt to re-author or cue these — they are free.

```
Layer 1 — Renderer (already active, no per-model work needed)
  • Auto-blinking       CubismEyeBlink, fires every ~3–6 s
  • Ambient head drift  CubismBreath on AngleX/Y/Z/BodyAngleX
  • Breathing / sway    same CubismBreath instance
  • Expression fade     CubismExpressionMotionManager (timing from .exp3.json)
  • Idle loop           auto-restarts Idle when nothing else is playing
```

What you must author (Layer 2):

```
Layer 2 — Authored assets (per-model; your responsibility)
  • Expression files    .exp3.json with correct parameter coverage + non-zero fade times
  • Idle motion         includes ParamEyeBallX/Y keyframes for ambient gaze drift
  • Reaction clips      nod, look_away, tap (threshold); shake (enhancement)
```

What the upstream manifest drives (Layer 3 — not authored here):

```
Layer 3 — Upstream cues (video_agent scene manifest)
  • emotion cues        switch expressions at script-appropriate moments
  • reaction cues       inject nod/look_away at discourse beats
  • gaze cues           held static positions only (raw cues snap — see warning below)
  • head cues           use with caution (see warning below)
```

### Warning: gaze cues snap

Raw `gaze` cues call `SetParameterValue` with no interpolation — the eye jumps instantly to the requested position. **Use raw gaze cues only for held static positions.** For smooth gaze transitions, use the `look_away` reaction clip, which animates `ParamEyeBallX/Y` via smooth keyframe curves.

- Ambient gaze drift → keyframed in the idle motion (`ParamEyeBallX/Y`)
- Deliberate look-away → `look_away` reaction clip animates eye movement smoothly
- Static gaze hold → raw `gaze` cue (acceptable for this case only)

### Warning: head cues may conflict with CubismBreath

`head` cues write to `AngleX/Y/Z` directly, then `CubismBreath` runs on the same parameters in the same update tick. Test this explicitly on the target model (Phase B3 below) before relying on raw head cues for any motion. Reaction clips avoid this issue entirely since they go through the motion priority system.

---

## Phase 0 — Prerequisites

Before authoring anything, confirm all of the following. Do not proceed until every item is satisfied.

1. The model has passed Stage 1 of `model-onboarding.md`, including the VTubeStudio Export Detour if applicable.
2. Expressions are authored and Stage 3 human-approved — the emotion mapping is complete in `registry.json`.
3. The renderer binary is built and has produced at least one successful test render on the target machine.
4. Read the model's `.cdi3.json` and enumerate all available parameter IDs. This is the parameter budget. Every parameter name used in any authored asset must come from this file. Never copy parameter names from another model.

---

## Phase 0.5 — Pre-authoring audit

Before writing any new files, check what Layer 2 assets already exist and whether existing assets are correct.

1. **Expression fade times** — Open each `.exp3.json`. Confirm `FadeInTime` ≥ 0.15 and `FadeOutTime` ≥ 0.3 on every file. Zero or missing values cause visible expression snaps — fix before the first review render. This is a correctness fix, not creative authoring; it does not require a human review round.

2. **Expression region coverage** — Confirm each expression file sets non-zero parameters in all three facial regions: brows, eyes, and mouth. Flag any expression that only moves the mouth.

3. **Idle motion quality** — Open the idle motion file. Confirm it covers at least `ParamAngleX` and `ParamAngleZ` with visible amplitude. Note whether `ParamEyeBallX/Y` keyframes are present — if absent, gaze drift must be added.

4. **Existing reaction clips** — List all `.motion3.json` files already present in the model directory. Identify which spec-required reactions are genuinely missing versus merely unregistered in `registry.json`.

Record all findings in `<model_dir>/audit.md` before proceeding.

---

## Phase B3 — Head cue conflict test (run before authoring reaction clips)

Before authoring any reaction clips, verify whether raw `head` cues work on this model:

1. Write a test manifest that sends explicit `head` cues (`AngleX` = +15°, `AngleY` = –10°) at known times, and a `gaze` cue, and a combined `emotion` + `reaction` cue.
2. Render it and inspect the output.
3. **Pass:** head moves visibly to the cued angle and holds → `head_cues_reliable = true`. Reaction clips may include head movement on keyframe curves (they always use keyframes regardless; this affects whether *raw cues* can supplement clips).
4. **Fail:** head stays in breath-cycle position regardless of cue values → `head_cues_reliable = false`. All head movement must be in motion clip keyframes; raw head cues are unreliable for this model.

Record the outcome. Brief the AssetAuthorAgent with it before dispatching reaction clip authoring.

---

## Phase 1 — Authoring

Author only the Layer 2 items identified as missing or broken in the Phase 0.5 audit.

For each required behaviour:

1. Read the spec item: target label, semantic intent, required parameters, duration, and tier.
2. Read the model's `.cdi3.json`. All parameter names and ranges must come from this file.
3. **Run a dedicated axis calibration render before authoring any motion clip.** See [Lesson 1](#lesson-1--verify-parameter-axes-with-a-calibration-render-before-authoring) below. Do not assume axis directions from parameter names — confirm them visually.
4. Read analogous motion files from the Cubism SDK sample models (e.g. Haru's `TapBody`, `Idle`) as **format templates only** — for JSON structure and curve encoding, not for parameter values or names.
5. Make a best-effort initial estimate of keyframe values based on physical plausibility. Document the rationale.
6. Write the file to `<model_dir>/motions/<label>.motion3.json` or `<model_dir>/expressions/<label>.exp3.json`.
7. Wire it into the model's `.model3.json` under `FileReferences.Motions` or `FileReferences.Expressions`. The group name in `Motions` must match the `id` in the registry entry exactly — see [Lesson 2](#lesson-2--registry-alias-to-motion-group-name-mapping-must-be-exact).
8. Record parameter choices and rationale in `<model_dir>/motions/README.md`.

### Expression file requirements

- `FadeInTime` ≥ 0.15 s (zero causes a visible snap)
- `FadeOutTime` ≥ 0.3 s
- Non-zero parameter deltas in all three regions: brows, eyes, mouth

### Motion file requirements

- `FadeInTime` ≥ 0.1 s
- `FadeOutTime` ≥ 0.5 s minimum (see [Lesson 3](#lesson-3--fadeouttimes-and-the-cubismbreath-snap)); ≥ 0.6 s for clips longer than ~1.0 s
- All parameter names derived from the model's own `.cdi3.json`

### Idle motion quality floor

- Visible head movement across its full duration (not a frozen hold)
- Covers at least `ParamAngleX` and `ParamAngleZ` with non-trivial amplitude
- ≥ 3 s before looping
- `ParamEyeBallX/Y` keyframes present for ambient gaze drift

### Reaction clip reference values (majo-calibrated)

The table below uses confirmed majo axis directions. For a new model, substitute the correct parameter IDs from its `.cdi3.json` after axis calibration.

| Label | Semantic intent | Key parameters | Duration | Tier |
|---|---|---|---|---|
| `idle` | Default ambient loop | `AngleX/Y/Z`, `BodyAngleX`, `ParamEyeBallX/Y` | Loops | Mandatory |
| `nod` | Discourse acknowledgement (standard) | Pitch axis — dip ~30–35% of range and return, up-then-down shape | ~1.5 s | Threshold |
| `deep_nod` | Emphatic acknowledgement | Pitch axis — dip ~50% of range | ~1.5 s | Enhancement |
| `look_away` | Thinking / recalling; breaks camera lock | `ParamEyeBallX/Y` smooth arc; head follow axis offset 150 ms behind, ~35% of eye amplitude | ~1.5 s | Threshold |
| `tap` | Startled / interaction reaction | Roll axis — jolt and damped oscillation | ~1.0 s | Threshold |
| `shake` | Disagreement | Roll axis — ±10–15°, two cycles | ~0.8 s | Enhancement |

**`look_away` must use smooth keyframe curves on the eye parameters — not a raw gaze cue.** The clip should show a smooth arc on eye movement, not a snap. If it does, gaze capability is confirmed.

**Minimum to pass spec:** `idle` + 3 threshold reactions (`nod`, `look_away`, `tap`).

### Breath guard field

When registering a reaction in `registry.json`, set `breath_guard` based on clip duration and amplitude:

| Situation | Setting | Effect |
|---|---|---|
| Short/low-amplitude clip (nod, tap) | `"breath_guard": "none"` | Breath runs freely; resumption is imperceptible at low amplitude |
| Long or large-amplitude clip (look_away, deep_nod) | omit (defaults to `"lerp"`) | Breath lerps back in over 0.5 s after the clip ends |
| Large-amplitude clip with a distinct FadeOut window (consult, lean_in) | `"breath_guard": "fadeout"` | Exit ramp arms when Cubism FadeOut starts (not after); duration = 2× the motion's FadeOutTime, so the guard is at 50% weight when priority drops and reaches 0 smoothly — eliminating the snap that occurs when both FadeOut and the guard end simultaneously |

See §7 above for full breath guard documentation.

---

## Phase 2 — Review render

Produce a labeled review video for each review round. Each clip must:

- Show **1 second of idle baseline** before the reaction triggers (so the reviewer sees the resting head position)
- Show the reaction
- Show **at least 5 seconds of idle after the reaction ends** (so the reviewer sees the full breath resumption and recovery)
- Carry a **top-center pass criteria overlay** (see below)
- Carry a **bottom-left animation state overlay** (see below)

Every clip must be at least 5 seconds total. Use a sentinel `{"time": T, "emotion": "neutral"}` cue to ensure the idle buffer renders.

Output target: `results/tests/<feature>/review_<feature>.mp4` (see [CLAUDE.md](../CLAUDE.md) for the full output convention).

If `scripts/behavior_review.py` does not support a required test case, write a one-off script or manifest for it. Do not block on script limitations.

### Required: top-center pass criteria overlay

Every review clip must burn the human review guidelines / PASS criteria as a **yellow text block centered at the top of the frame** (approximately `y=40`). This tells the reviewer what to look for *before* they watch. The overlay is always visible for the full clip duration.

Format: a single line or short phrase summarizing what PASS looks like. Example:

```
PASS: +14deg tilt + eye drop, smooth return. No snap at exit. No wobble during hold.
```

FFmpeg drawtext: `fontcolor=yellow`, `x=(w-tw)/2`, `y=40`, `box=1`, no `enable` expression (always shown).

### Required: bottom-left animation state overlay

Every review clip must burn a stacked **bottom-left animation state display** showing which animations are currently active, with countdown timers where applicable. This gives the reviewer a real-time reference for which phase is playing at any moment.

**Stack layout** (grows upward from the bottom-left, one line per animation layer, ~43px per line):

| Layer | Text format | Visibility | Color |
|---|---|---|---|
| Idle | `idle  [looping]` | Always | red |
| Reaction hold phase | `<name>  HOLD : Xs remaining` | Hold window only | red |
| Reaction fadeout phase | `<name>  FADEOUT : Xs remaining` | FadeOut window only | red |
| Breath guard (suppressed) | `breath-guard  SUPPRESSED  (w=1.00)` | Entry fade end → FadeOut start | orange |
| Breath guard (fading out) | `breath-guard  FADEOUT  w=X.XX` | FadeOut guard window | orange |
| Cubism FadeOut | `cubism-FadeOut : Xs  <- guard continues after this` | Cubism FadeOut window | cyan |

**Rules:**
- Each label disappears when its phase ends (use `enable='between(t\,X\,Y)'`)
- Idle has no countdown (it loops indefinitely)
- If multiple animation layers are simultaneously active, list all of them (one line each)
- Countdown text must be pre-computed in Python at ≤ 0.1s granularity — do **not** use FFmpeg `eif` with `'f'` format; it is not supported in FFmpeg 4.4. Use static text strings generated in Python via a helper like `_seq()` in `scripts/consult_review.py`

**Reference implementation:** `scripts/consult_review.py` — the `build_vf()` function and `_seq()` helper are the canonical pattern for building this overlay. Copy and adapt for other review scripts.

### Required: review description sheet

**Before asking the human to watch any review video, write a description sheet as text in your response.** The human reads this first, then watches the video. Do not send the video path alone — a reviewer who does not know what to look for cannot give useful feedback.

For each clip in the review, provide a row in this table:

| Clip | What it does | PASS looks like | FAIL looks like |
|------|-------------|-----------------|-----------------|
| ... | ... | ... | ... |

If you cannot describe pass/fail criteria for a behavior, go back to the authoring notes before generating the review — undefined criteria means the design intent was not documented clearly enough.

**Standard criteria for base behaviors:**

| Clip | What it does | PASS | FAIL |
|------|-------------|------|------|
| `idle` | Default ambient loop | Visible breathing and head movement; gaze drifts; no frozen frames | Head frozen or held at one position |
| `nod_review` | **Internal artifact — NOT a discourse nod.** Holds the head at a downward pitch for ~3.5s. Used to inspect breath resumption after a long hold. | Head eases smoothly back to neutral at the end; no visible jolt or snap | Sharp discontinuity when the hold ends |
| `nod` | Standard discourse acknowledgement | Head dips smoothly ~30–35% of pitch range, brief upward rebound, returns to neutral over ~1.5s; clean exit | Dip too deep (looks like a bow), too shallow (invisible), or snaps on exit |
| `deep_nod` | Emphatic acknowledgement | Visibly larger dip than `nod` (~50% of pitch range); same smooth shape and clean exit | Indistinguishable from `nod`, or snaps on exit |
| `look_away` | Thinking/recalling gaze shift | Head turns smoothly to one side, brief pause, then eases gradually back to center; no jolt at exit | Return is too fast (snap), or there is a discontinuity when the motion ends |
| `tap` | Startled or touch-response reaction | Brief sudden jolt with damped oscillation settling smoothly to neutral; feels like physical impact | Oscillation doesn't feel physical, or there is a jump/snap at the end |

**For persona-specific behaviors**, derive criteria from the design intent recorded at authoring time. See the Sable spec entries below as an example of the required level of specificity.

**Standard criteria for Sable spec v1.1 behaviors:**

| Clip | What it does | PASS | FAIL |
|------|-------------|------|------|
| `wry` | Dry-wit knowing smile | More mouth curve than neutral but less than happy; eyes very slightly narrowed (alert, not squinting); brow barely raised; overall read: "I know something you don't" | Indistinguishable from neutral, or reads as happy |
| `grave` | Solemn authority | Eyes fully open (holds your gaze); faint downward set to the mouth; barely perceptible brow tension; heavier than neutral but not sad | Looks identical to neutral, or reads as sad |
| `hushed` | Conspiratorial narrowing | Eyes noticeably more hooded than neutral but not bored-level; mouth less curved than neutral (near-flat, not frowning) | Indistinguishable from neutral or bored |
| `contemptuous` | Mildly superior affectionate contempt | Slight brow furrow (not angry), slight upward mouth curve (smug), eyes slightly narrowed | Reads as angry, or indistinguishable from wry |
| `lean_in` | Key-revelation cue | Head dips very gradually (~1.2s to peak), holds ~1s, eases slowly back; unhurried and deliberate; no rebound; smooth exit | Onset too fast (reads as nod), has a rebound, or snaps on exit |
| `consult` | Chapter-open / "let me find the file" | Head tilts to one side while eyes shift slightly downward as if reading; holds briefly; eases smoothly back | Tilts wrong direction, too fast, or snaps on exit |
| `glance_down` | Historical-gap self-deprecating beat | Eyes drop quickly, hold ~0.4s, return; head dips slightly later than eyes; total ~1.4s; punchy and brief | Too slow (loses the punctuation quality), holds too long, or snaps on exit |
| `address` | Correction-of-historians direct address | Head eases to face camera (yaw centering) with a slight chin-up lift; most legible when triggered from an off-center position (e.g. after `look_away`) | No visible yaw centering, chin-up absent, or too abrupt |

---

## Phase 3 — Human review

The human watches the video and provides plain-English feedback. The agent interprets it and writes the structured record — the human never fills out schemas.

After receiving feedback:

1. Re-read the review manifest to recall which clip is which.
2. Determine verdict for each clip: Explicit praise / no complaint → `Approved`. Any criticism → `Revise`. Ambiguous → `Revise`. Not mentioned → `Approved` only if human said "everything else looks good", otherwise `Unreviewed`.
3. For `Revise` clips: map visual observations to parameters. See [Lesson 4](#lesson-4--verify-parameter-values-in-the-actual-file-before-recording-a-round-log-diagnosis).
4. Populate and write `<model_dir>/review_log/round_<N>.json` **before** making any edits.

Collect all feedback for the current round before starting any revisions.

---

## Phase 4 — Revision loop

For each clip with `"verdict": "Revise"`:

1. Apply the proposed fix.
2. Save the previous version as `<filename>_v<N-1>.json` — do not overwrite only.
3. Re-render only the affected clips (targeted manifest, not the full set). Label with `[REVISED r<N>]`.
4. Human reviews only the changed clips.
5. Record the new round in `round_<N+1>.json`.
6. Repeat until `Approved` or `Drop`.

**Stopping rule:** if the same clip has been revised 3 or more times without approval, stop and ask the human explicitly: "Should I continue iterating on this behaviour, or drop it?" Do not proceed to a fourth revision without a clear instruction.

---

## Phase 5 — Registry update

Once all behaviours are resolved:

1. Update `assets/models/registry.json` with approved `emotions` and `reactions` entries.
2. For dropped items, add a `"gaps"` field documenting what was dropped and why.
3. Run the full test fixture suite to confirm no regressions.

---

## Phase 6 — Spec compliance check

Verify the model meets Avatar Behaviour Spec v1.

**Expressions — mandatory (4):**
- `neutral` — brows level, eyes ~0.9 openness, mouth flat or slight upward curve
- `happy` — raised brows, Duchenne eye squint, upward mouth curve
- `serious` — lowered brows (not angry), slight eye reduction, flat or slight downward mouth
- `surprised` — raised brows, widened eyes, slight open mouth

**Expressions — threshold (mandatory + 2):**
- `sad` — arched inward brows, softened eyes, downturned mouth
- `angry` — furrowed down brows, narrowed eyes, tight downturned mouth

**Reactions — minimum:**
- `idle` — visible head movement, `ParamAngleX` + `ParamAngleZ` covered, ≥ 3 s loop, `ParamEyeBallX/Y` gaze drift
- `nod` — dip and return on the pitch axis, ~1.5 s
- `look_away` — smooth eye arc, head follow offset, ~1.5 s
- `tap` — jolt and recovery on the roll axis, ~1.0 s

Also verify: fade times on all files, parameter names from `.cdi3.json`, `look_away` uses smooth keyframe curves, head cue conflict tested and documented.

If any minimum is not met, escalate:
> "This model cannot meet spec minimum [X] because [reason]. Options: (A) continue iteration, (B) accept as a limited model with documented gap, (C) reject model."

---

## File locations summary

| Asset | Path |
|---|---|
| Pre-authoring audit | `<model_dir>/audit.md` |
| Expression files | `<model_dir>/expressions/<label>.exp3.json` |
| Motion clips | `<model_dir>/motions/<label>.motion3.json` |
| Motion authoring notes | `<model_dir>/motions/README.md` |
| Review round logs | `<model_dir>/review_log/round_<N>.json` |
| Model registry | `assets/models/registry.json` |
| Review render output | `results/tests/<feature>/` |

---

## Lessons from majo (Reference Implementation)

Majo was the first model walked through this workflow (2026-03-17–18). The following lessons update or refine the phases above based on what actually happened.

---

### Lesson 1 — Verify parameter axes with a calibration render before authoring

**What happened:** The first nod clip (v0) used `ParamAngleX` for the dip. Visual calibration confirmed `ParamAngleX` is left/right yaw — not the nod (pitch) axis. The correct parameter was `ParamAngleY`. This required two additional revision cycles before the nod shape was correct.

**Rule:** Before authoring any motion clip, render a dedicated calibration clip that drives each candidate parameter in isolation and confirm the axis direction visually. For majo the confirmed axes are:

| Parameter | Axis | Sign |
|---|---|---|
| `ParamAngleX` | Left/right yaw | + = turn right |
| `ParamAngleY` | Up/down pitch | + = look up, − = look down / nod dip |
| `ParamAngleZ` | Tilt/roll | + = lean right |
| `ParamEyeBallX` | Gaze horizontal | + = right |
| `ParamEyeBallY` | Gaze vertical | + = up |

For a new model, do not assume these mappings — calibrate first.

---

### Lesson 2 — Registry alias to motion group name mapping must be exact

**What happened:** Round 1 review found all three reaction clips looked identical to idle. Root cause: the cue sequencer dispatched the alias (e.g. `nod`) to the registry to get the raw group name, then looked up that group name in the model3.json `Motions` block. If the raw group name in the registry does not exactly match the key in model3.json, the motion silently does not fire.

**Rule:** Before any review render, verify the chain: `registry.json reaction alias → raw_id → model3.json Motions key`. All three must be consistent. A mismatch produces no error — the model continues playing idle, which looks identical to a broken reaction.

---

### Lesson 3 — FadeOutTimes and the CubismBreath snap

**What happened:** All three reaction clips showed a visible snap or jolt when the motion ended. Root cause: when a reaction ends, CubismBreath resumes at whatever phase it is currently at. If the breath is mid-oscillation, the head can jump discontinuously.

**Mitigations applied:**
1. **Lerp breath guard** — the renderer lerps breath back in over 0.5 s after a reaction ends, softening the snap. Enabled by default for all reactions.
2. **Longer FadeOutTime** — increasing the motion's FadeOutTime extends the blend-out window, giving the lerp guard more time to work. Set ≥ 0.5 s for short reactions; ≥ 0.6 s for reactions ≥ 1.0 s.
3. **`breath_guard: "none"` for low-amplitude reactions** — for subtle, short reactions (nod-level amplitude), disabling the guard and letting breath run freely produces a cleaner result because the breath resumption is imperceptible at that amplitude.

**Rule:** Default all reaction clips to `FadeOutTime ≥ 0.5 s` during initial authoring. Use `breath_guard: "none"` for reactions with peak amplitude below ~35% of the parameter range.

---

### Lesson 4 — Verify parameter values in the actual file before recording a round log diagnosis

**What happened:** The round_2.json diagnosis for `nod` referenced `ParamAngleX` (wrong axis) and a peak value of −10 "to be reduced to −7". The actual file used `ParamAngleY` and had a peak of −22. The diagnosis was written from memory rather than from reading the file, leading to an incorrect proposed fix.

**Rule:** Before writing any `agent_diagnosis` or `proposed_fix` to a round log, open the actual `.motion3.json` or `.exp3.json` and read the current values. Never diagnose from memory. The round log must reference what the file actually contains at the time of diagnosis.

---

### Lesson 5 — Nod amplitude and the two-tier nod system

**What happened:** The initial nod had a peak of −22° on `ParamAngleY` (73% of the ±30 range). Human review: "a lot of motion / looking down." Reduced to −10° (33% of range) — approved. A second, lower-amplitude variant (peak −5°, 17% of range) was added and made the default `nod` because script writers producing discourse nods expect a subtle acknowledgement, not an emphatic dip.

**Rule for nod amplitude:**
- Standard discourse nod: 30–35% of the pitch range (peak ~−10° for a ±30 model)
- Emphatic nod: ~50% of range
- Register both as `nod` (standard) and `deep_nod` (emphatic). Script writers default to `nod`.

---

### Lesson 6 — look_away head follow axis

**What happened:** `look_away.motion3.json` uses `ParamAngleY` (+7°) for head follow as the eyes go right. `ParamAngleY` is pitch (up/down), so the head lifts slightly as the eyes move right — producing an "up-right thinking gaze." This was identified as a known quirk (lateral head follow would use `ParamAngleX`), but the human reviewer approved the overall read as plausible. Not corrected.

**Note for future models:** for a natural lateral look-away, the head follow should use the yaw axis (`ParamAngleX` or equivalent), not the pitch axis. The look_away template is: eye axis at full deflection, head follow on the yaw axis at ~35% of eye amplitude, offset ~150 ms behind the eye peak.

---

### Lesson 7 — Reaction vocabulary naming convention

Script-writing agents use reaction labels when composing scene manifests. The label `nod` is the one they will default to for any discourse acknowledgement beat. Name the standard (subtle) version `nod` and reserve more expressive variants for explicit labels like `deep_nod`. This prevents script writers from unintentionally triggering an emphatic reaction when they want a light acknowledgement.

---

### Lesson 8 — Fast linear return segments cause perceived snap, even with lerp guard

**What happened:** `look_away` (Sable sable_r1 review) had a visible snap at the end despite the lerp breath guard being active. Root cause: the motion curve returned AngleX from 20° to 0° linearly over 0.5s — a rate of 40°/s — which reads as abrupt. The lerp guard suppresses the *breath resumption* snap, but it does not smooth out a fast in-curve return within the motion itself.

The same pattern recurred in `consult` (AngleZ 12° → 0° over 0.7s) and `glance_down` (AngleY −4° → 0° over 0.35s).

**Pre-existing defect:** `look_away` and `tap` had this issue from initial authoring but it was not caught in review rounds 1–3 because no review description told the reviewer what a clean exit should look like.

**Rule:** The return-to-zero phase of any motion clip should take approximately the same time as the onset phase. A clip that eases in over 0.5s should ease out over at least 0.5s. For large-deflection clips (>10° or >50% of the parameter's breath amplitude), the return phase should be ≥ 1.0s.

**Updated FadeOutTime guidance:** For clips whose motion curve includes a return-to-zero segment, the motion-group FadeOutTime in `model3.json` should be set to ≥ the lerp guard duration (0.5s) plus the per-curve FadeOutTime. For large-amplitude clips, use 1.0s at the motion-group level.

---

### Lesson 9 — Review overlay standard: pass criteria at top, animation state at bottom-left

**What happened:** Early review rounds produced clips with no on-screen guidance, requiring the agent to write a separate description sheet the human had to cross-reference while watching. Later clips (starting with `consult_phase_review.mp4`) burned pass criteria at the top and a live animation state display at the bottom-left. Reviewers could immediately see what to look for and verify which animation layer was responsible for any artifact they observed.

**Rule:** Every review clip must carry two burned-in overlays:

1. **Top-center (yellow):** human review guidelines / PASS criteria — always visible, concise summary of what PASS looks like.
2. **Bottom-left (stacked, color-coded):** live animation state with countdown timers. Idle is always listed with `[looping]`. Reaction phases (HOLD, FADEOUT) show time remaining and disappear when the phase ends. Breath guard state is shown in orange; Cubism FadeOut in cyan.

**Why this matters:** The snap that prompted the `breath_guard:"fadeout"` investigation was only precisely located because the overlay showed the guard reaching 0 at exactly the same frame FadeOut ended. Without the overlay, it would have been described as "a glitch around exit" and harder to trace to the simultaneous termination of two separate systems.

**Implementation:** `scripts/consult_review.py` is the reference. The `build_vf()` function builds the full filter chain; `_seq()` generates static text entries at 0.1s granularity to work around FFmpeg 4.4's lack of float format in `eif`. Copy and adapt this pattern for all future review scripts.

---

### Lesson 10 — Per-curve FadeOutTime must be 0.0 for curves that explicitly return to zero when using fade_to_idle

**What happened:** `look_away` showed a visible head snap at the exact frame that `fade_to_idle` began — not at the end (which was already fixed), but at the very start. The snap remained even after all other fixes were in place.

**Root cause:** Cubism's per-curve FadeOut blending does not write the curve's keyframe value directly. Instead it blends toward it each frame using: `s(t) = fw × mv + (1−fw) × s(t−dt)`, where `fw` is the FadeOut weight (0→1 as the motion ends) and `mv` is the motion value. With `GetEasingSine` (ease-in-out), `fw` approaches 1 asymptotically — barely moving near the end. For `look_away` with `FadeOutTime=1.0`, the saved state converged to **6.07°** at motion end, not 0°. The `fade_to_idle` lerp started from that 6.07° snapshot at −6.07°/s, while the motion had been exiting at only −0.45°/s — a 13× velocity jump that reads as a snap.

**Fix:** Set `"FadeOutTime": 0.0` on any curve whose keyframe sequence already returns explicitly to its default value (e.g. the curve ends with a `0.0` keyframe). With `FadeOutTime=0.0`, the FadeOut weight is always 1.0, so the final keyframe value is written cleanly into `_savedParameters` — zero residual, zero snap.

**Rule:** For any reaction clip that uses `fade_to_idle: true`:
- Curves that animate away and explicitly return to 0 in their keyframe sequence → set `FadeOutTime: 0.0`
- Curves that do NOT return to their default in the keyframe sequence → keep `FadeOutTime > 0` (the FadeOut window blends them back to idle)

**Concrete change:** `look_away.motion3.json`, `ParamAngleX` curve: `"FadeOutTime": 1.0` → `"FadeOutTime": 0.0`.
