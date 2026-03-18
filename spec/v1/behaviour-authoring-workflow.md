# Behaviour Authoring Workflow
Status: Draft
Spec version: 1.0 (2026-03-17)

---

## Purpose

This document is the step-by-step guide for authoring behaviours for any new Live2D model. Follow it whenever a model needs Layer 2 assets built from scratch — typically any VTubeStudio-origin model that has no existing motion clips or expression files.

The workflow is a cycle: **agent proposes → renders review video → human reviews → agent refines → repeat.** It runs from initial prerequisites through spec compliance sign-off.

---

## Background: What you do and do not need to author

The renderer already provides several behaviours unconditionally for any correctly configured model. Do not attempt to re-author or cue these — they are free.

```
Layer 1 — Renderer (already active, no per-model work needed)
  • Auto-blinking       CubismEyeBlink, fires every ~3–6 s
  • Ambient head drift  CubismBreath on AngleX/Y/Z/BodyAngleX
  • Breathing / sway    same CubismBreath instance
  • Expression fade     CubismExpressionMotionManager (timing from .exp3.json)
  • Idle loop           auto-restarts Idle_0 when nothing else is playing
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

Raw `gaze` cues call `SetParameterValue` with no interpolation — the eye jumps instantly to the requested position. **Use raw gaze cues only for held static positions.** For smooth gaze transitions, use the `look_away` reaction clip, which animates `ParamEyeBallX/Y` via smooth keyframe curves. Specifically:

- Ambient gaze drift → keyframed in the idle motion (`ParamEyeBallX/Y`)
- Deliberate look-away → `look_away` reaction clip animates eye movement smoothly
- Static gaze hold → raw `gaze` cue (acceptable for this case only)

### Warning: head cues may conflict with CubismBreath

`head` cues write to `AngleX/Y/Z` directly, then `CubismBreath` runs on the same parameters in the same update tick. Whether breath overwrites or blends with cue values is unverified. Until this is confirmed working for the target model, prefer reaction clips for all head movement — reaction clips go through the motion priority system and avoid this conflict.

---

## Phase 0 — Prerequisites

Before authoring anything, confirm all of the following are true. Do not proceed to Phase 0.5 until every item is satisfied.

1. The model has passed Stage 1 of `model-onboarding.md`, including the VTubeStudio Export Detour if applicable (which produces the initial expression set).
2. Expressions are authored and Stage 3 human-approved — the emotion mapping is complete in `registry.json`.
3. The renderer binary is built and has produced at least one successful test render on the target machine.
4. Read the model's `.cdi3.json` and enumerate all available parameter IDs. This is the parameter budget. Every parameter name used in any authored asset must come from this file. Never copy parameter names from another model.

---

## Phase 0.5 — Pre-authoring audit

Before writing any new files, check what Layer 2 assets already exist and whether existing assets are correct. This prevents unnecessary authoring work.

Perform each check and record the result:

1. **Expression fade times** — Open each `.exp3.json` for the model. Confirm `FadeInTime` ≥ 0.15 and `FadeOutTime` ≥ 0.3 on every file. If any value is zero or missing, flag it for correction before the first review render. This is a correctness fix, not creative authoring — it does not require a human review round.

2. **Expression region coverage** — For each expression file, confirm that parameter deltas are non-zero in all three facial regions: brows, eyes, and mouth. Flag any expression that only moves the mouth.

3. **Idle motion quality** — Open the idle motion file. Confirm it covers at least `ParamAngleX` and `ParamAngleZ` with visible (non-trivial) amplitude. Note whether `ParamEyeBallX` and `ParamEyeBallY` keyframes are present — if absent, the idle motion needs gaze drift added.

4. **Existing reaction clips** — List all `.motion3.json` files already present in the model directory. Identify which spec-required reactions are genuinely missing versus merely unregistered in `registry.json`.

Record all findings in `<model_dir>/audit.md` before proceeding to Phase 1.

---

## Phase 1 — Authoring

Author only the Layer 2 items identified as missing or broken in the Phase 0.5 audit. Do not re-author anything the renderer already provides.

For each required behaviour, follow these steps in order:

1. Read the spec item: target label, semantic intent, required parameters, duration, and tier. (Tier definitions: **Mandatory** = required for spec compliance; **Threshold** = required for NPC realism threshold; **Enhancement** = optional.)

2. Read the model's `.cdi3.json`. All parameter names and value ranges must come from this file. Never copy parameter names from another model's files.

3. Read analogous motion files from the Cubism SDK sample models (for example, Haru's `TapBody` or `Idle` motions) as **format templates only** — for JSON structure and curve encoding, not for parameter values or names.

4. Make a best-effort initial estimate of keyframe values based on physical plausibility. Document the rationale alongside the file.

5. Write the file to the appropriate location:
   - Motion clips → `<model_dir>/motions/<label>.motion3.json`
   - Expressions → `<model_dir>/expressions/<label>.exp3.json`

6. Wire the new file into the model's `.model3.json` under the appropriate `FileReferences` key.

7. Record parameter choices and rationale in `<model_dir>/motions/README.md`.

### Expression file requirements

Every `.exp3.json` must satisfy:
- `FadeInTime` ≥ 0.15 s (zero causes a visible snap)
- `FadeOutTime` ≥ 0.3 s
- Non-zero parameter deltas in all three regions: brows, eyes, mouth

### Motion file requirements

Every `.motion3.json` must satisfy:
- `FadeInTime` ≥ 0.1 s
- `FadeOutTime` ≥ 0.1 s
- All parameter names derived from the model's own `.cdi3.json`

### Idle motion quality floor

The idle motion (`Idle_0`) must:
- Produce visible head movement across its full duration (not a frozen hold)
- Cover at least `ParamAngleX` and `ParamAngleZ` with non-trivial amplitude
- Be ≥ 3 s before looping
- Include `ParamEyeBallX/Y` keyframes for ambient gaze drift (slight variation away from center)

Note: `CubismBreath` adds sinusoidal drift on top of the idle motion. The idle motion does not need to do heavy lifting on head movement, but it must not hold a fixed target that fights the breath layer.

### Reaction clip reference values

The following are conceptual starting points. Derive the actual parameter names from the model's `.cdi3.json` — the names below are conventional identifiers that may or may not match any given model's parameter budget.

| Label | Semantic intent | Key parameters | Duration | Tier |
|---|---|---|---|---|
| `idle` | Default ambient loop | `AngleX/Y/Z`, `BodyAngleX`, `ParamEyeBallX/Y` | Loops | Mandatory |
| `nod` | Discourse acknowledgement; sentence completion | `ParamAngleX` — dip –10 to –15° and return | ~0.5 s | Threshold |
| `look_away` | Thinking / recalling; breaks camera lock | `ParamEyeBallX/Y` on smooth curves; `ParamAngleY` offset ~150 ms behind eye, ~30–40% of eye amplitude | ~1.5 s | Threshold |
| `tap` | Startled / interaction reaction | `ParamAngleZ` — jolt and recovery | ~1.0 s | Threshold |
| `shake` | Disagreement / no | `ParamAngleZ` ±10–15°, two cycles | ~0.8 s | Enhancement |

**`look_away` must use smooth keyframe curves on the eye parameters — not a raw gaze cue.** The rendered clip should show a smooth arc on eye movement, not a snap. If it does, gaze capability for this model is confirmed.

**Minimum to pass spec:** `idle` + 3 threshold reactions (`nod`, `look_away`, `tap`).

---

## Phase 2 — Review render

Produce a labeled review video so the human reviewer can evaluate each behaviour in isolation.

The preferred tool is `scripts/behavior_review.py`, which renders one segment per emotion and reaction and burns text labels via FFmpeg.

If the review script is insufficient for a specific test case (for example, gaze or head cue testing, or physics verification), do not block — design an alternative:

1. Write a one-off test manifest targeting only the specific behaviour.
2. Render it directly via the renderer binary.
3. Post-process the output with FFmpeg to annotate the clip with the behaviour label.

### Required: explanatory text overlay

Every render produced for human review **must** include a text blurb at the top of the frame explaining what the motion is supposed to do and what to look for. The human reviewer cannot give useful feedback on an unlabelled clip.

Use FFmpeg `drawtext` filters to burn a semi-transparent bar at the top of the frame (~100px height) containing:
- A **title line** naming the behaviour being tested (e.g., `HEAD CUE CONFLICT TEST`, `NOD REACTION`, `FULL BEHAVIOUR REVIEW — ROUND 1`)
- A **description line** in plain English: what the avatar should do, and what a passing result looks like

Leave enough vertical padding (~80–100px from the top) so the text does not overlap the avatar's face.

Also burn a **visible timestamp** (e.g. `t=0.00s`) into a corner of the frame, updating every frame. This allows the reviewer to pause the video at any point and know the exact time, which is essential for mapping visual observations to the feedback record.

Apply all of the above to every type of render: full review renders, targeted re-renders, one-off test manifests, and gate verification renders. No render sent to the human should lack this context.

The goal is a labeled video where each behaviour is visually isolated, named, and explained, making the human review in Phase 3 as fast as possible.

---

## Phase 3 — Human review

The human watches the review video and provides verbal or written feedback in plain English. The agent is responsible for interpreting that feedback and translating it into the structured feedback record below. The human does not fill out any schema.

After receiving feedback, do the following before making any edits:

1. Re-read the review video manifest to recall which clip corresponds to which behaviour.

2. For each clip the human mentioned, determine the verdict from context:
   - Explicit praise or no complaint → `"Approved"`
   - Any criticism or suggestion for change → `"Revise"`
   - Ambiguous phrasing (e.g., "that looks a bit off") → `"Revise"`
   - Not mentioned → treat as `"Approved"` only if the human explicitly said "everything else looks good"; otherwise leave unresolved and ask

3. For each `"Revise"` clip: identify the specific parameter or timing change needed. Map visual observations to parameters (for example, "the nod goes too deep" → `ParamAngleY` peak magnitude too large). If the human's description is genuinely ambiguous, ask one clarifying question before proceeding — do not guess blindly at parameter changes.

4. Populate the feedback record using this schema:

```json
{
  "round": 1,
  "clips": [
    {
      "label": "nod",
      "type": "reaction",
      "verdict": "Revise",
      "human_quote": "the nod goes too deep, looks like a bow",
      "agent_diagnosis": "ParamAngleY peak magnitude too large",
      "proposed_fix": "Reduce ParamAngleY from -20 to -10"
    },
    {
      "label": "blink",
      "type": "reaction",
      "verdict": "Approved",
      "human_quote": null,
      "agent_diagnosis": null,
      "proposed_fix": null
    }
  ]
}
```

5. Write the record to `<model_dir>/review_log/round_<N>.json` before making any edits. This creates a traceable history of what was changed and why.

Collect all feedback for the current round before starting any revisions.

---

## Phase 4 — Revision loop

For each clip with `"verdict": "Revise"` in the current round log:

1. Apply the `proposed_fix` to the `.motion3.json` or `.exp3.json`.

2. Save the previous version as `<filename>_v<N-1>.json` alongside the new file — do not overwrite-only. This allows rollback if the revision makes things worse.

3. Re-render only the affected clips. Write a targeted manifest containing only those cues, not the full behaviour set. Produce a short labeled video for each changed clip.

4. Send the targeted video to the human for review of only the changed clips.

5. Record the new round in `round_<N+1>.json`.

6. Repeat until all clips reach `"verdict": "Approved"` or `"verdict": "Drop"`.

**Stopping rule:** if the same clip has been revised 3 or more times without approval, stop and explicitly ask the human: "Should I continue iterating on this behaviour, or drop it?" Do not proceed to a fourth revision without a clear instruction to do so.

---

## Phase 5 — Registry update

Once all behaviours are resolved (approved or dropped with a documented reason):

1. Update `assets/models/registry.json` with new `emotions` and `reactions` entries for all approved items.

2. For any dropped items, add a `"gaps"` field to the model's registry entry documenting what was dropped and why (for example: parameter budget too limited, behaviour indistinct from another expression).

3. Run the full test fixture suite to confirm no regressions.

---

## Phase 6 — Spec compliance check

Verify that the model meets Avatar Behaviour Spec v1.

Check each of the following against the approved behaviour set:

**Expressions — minimum to pass spec (4 mandatory):**
- `neutral` — resting default; brows level, eyes ~0.9 openness, mouth flat or slight upward curve
- `happy` — raised brows, Duchenne eye squint, upward mouth curve
- `serious` — lowered brows (not angry), slight eye reduction, flat or slight downward mouth
- `surprised` — raised brows, widened eyes, slight open mouth

**Expressions — threshold set (mandatory + 2 more):**
- `sad` — arched inward brows, softened eyes, downturned mouth
- `angry` — furrowed down brows, narrowed eyes, tight downturned mouth

**Reactions — minimum to pass spec:**
- `idle` — visible head movement, covers `ParamAngleX` and `ParamAngleZ`, ≥ 3 s loop, includes `ParamEyeBallX/Y` gaze drift
- `nod` — dip and return on the forward/back angle axis, ~0.5 s
- `look_away` — smooth curve on `ParamEyeBallX/Y`, head follow offset, ~1.5 s
- `tap` — jolt and recovery on the tilt axis, ~1.0 s

Also verify:
- All expression files have `FadeInTime` ≥ 0.15 s and `FadeOutTime` ≥ 0.3 s
- All motion files have `FadeInTime` ≥ 0.1 s and `FadeOutTime` ≥ 0.1 s
- All parameter names in authored files are derived from the model's `.cdi3.json`
- The `look_away` clip uses smooth keyframe curves on eye parameters (not a raw gaze cue)
- The head cue conflict (CubismBreath vs. raw head cues) has been tested and the outcome documented

Document the compliance result in the model's registry entry.

If the minimum is not met, do not silently accept the gap. Escalate to the human with a clear statement:

> "This model cannot meet spec minimum [behaviour] because [reason]. Options: (A) continue iteration, (B) accept as a limited model with documented gap, (C) reject model."

Wait for an explicit instruction before proceeding.

---

## Quick reference: compliance tiers

| Tier | Meaning |
|---|---|
| **Mandatory** | Required for spec compliance. Model fails onboarding without these. |
| **Threshold** | Required for NPC realism threshold. Absence reads as "cheap web avatar." |
| **Enhancement** | Optional. Adds richness; not required. |

**Minimum to pass spec:** 4 mandatory expressions + idle + 3 threshold reactions.
**Threshold set:** mandatory expressions + sad + angry expressions; idle + nod + look_away + tap reactions.

---

## File locations summary

| Asset type | Path |
|---|---|
| Pre-authoring audit | `<model_dir>/audit.md` |
| Expression files | `<model_dir>/expressions/<label>.exp3.json` |
| Motion clips | `<model_dir>/motions/<label>.motion3.json` |
| Motion authoring notes | `<model_dir>/motions/README.md` |
| Review round logs | `<model_dir>/review_log/round_<N>.json` |
| Model registry | `assets/models/registry.json` |
