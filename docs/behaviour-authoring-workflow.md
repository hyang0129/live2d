# Behaviour Authoring Workflow

**Status:** Draft — pending D2 sign-off
**Spec version:** 1.0 (2026-03-17)
**Reference implementation:** majo (completed 2026-03-18)

---

## Purpose

This document is the step-by-step guide for authoring Layer 2 behaviours for any new Live2D model. Follow it whenever a model needs motion clips or expression files built from scratch — typically any VTubeStudio-origin model that has no existing authoring.

The workflow is a cycle: **agent proposes → renders review video → human reviews → agent refines → repeat.** It runs from initial prerequisites through spec compliance sign-off.

For the registry entry format, motion file format, expression file format, and breath guard configuration, see [authoring-guide.md](authoring-guide.md). This document covers *process*; the authoring guide covers *format*.

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
| Long or large-amplitude clip (look_away) | omit (defaults to `"lerp"`) | Breath lerps back in over 0.5 s after the clip ends |

See [authoring-guide.md §7](authoring-guide.md) for full breath guard documentation.

---

## Phase 2 — Review render

Produce a labeled review video for each review round. Each clip must:

- Show **1 second of idle baseline** before the reaction triggers (so the reviewer sees the resting head position)
- Show the reaction
- Show **at least 5 seconds of idle after the reaction ends** (so the reviewer sees the full breath resumption and recovery)
- Carry a text overlay: clip label + round number (e.g. `NOD [r1]`)
- Carry an explanatory sub-line: what the clip should do and what a passing result looks like
- Carry a **visible timestamp** (e.g. `t=0.00s`) in a corner, updating every frame

Every clip must be at least 5 seconds total. Use a sentinel `{"time": T, "emotion": "neutral"}` cue to ensure the idle buffer renders.

Output target: `results/tests/<feature>/review_<feature>.mp4` (see [CLAUDE.md](../CLAUDE.md) for the full output convention).

If `scripts/behavior_review.py` does not support a required test case, write a one-off script or manifest for it. Do not block on script limitations.

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
