# Avatar Behaviour Spec v1

**Version:** 1.0
**Date:** 2026-03-17
**Machine-readable spec:** [`avatar-behaviour-spec.json`](avatar-behaviour-spec.json)

---

## Overview

This spec defines the minimum behaviour vocabulary every registered Live2D model must support. It is the contract between model authoring and upstream cue generation.

Three audiences:
- **Model authors** — what must be built and validated for each model
- **video_agent / AvatarCueAgent** — what cue labels are safe to emit and when to use them
- **Human reviewers** — what to look for when approving authored behaviours

The companion JSON file (`avatar-behaviour-spec.json`) is the authoritative machine-readable form. This document is the human-readable explanation.

---

## Layer Model

Behaviours come from three sources. Understanding this prevents redundant work.

```
Layer 1 — Renderer (free, unconditional — do not cue these)
  • Auto-blinking       CubismEyeBlink, fires every ~3–6 s
  • Ambient head drift  CubismBreath on AngleX/Y/Z/BodyAngleX
  • Breathing / sway    same CubismBreath instance
  • Expression fade     CubismExpressionMotionManager (timing from .exp3.json)
  • Idle loop           auto-restarts Idle_0 when nothing else is playing

Layer 2 — Authored assets (per-model; built, tested, and reviewed in this repo)
  • Expression files    .exp3.json files with correct parameter coverage
  • Idle motion         ambient gaze drift (ParamEyeBallX/Y keyframes) included
  • Reaction clips      nod, look_away, tap (threshold); shake (enhancement)

Layer 3 — Upstream cues (video_agent drives via scene manifest)
  • emotion cues        switch expressions at script-appropriate moments
  • reaction cues       inject nod/look_away at discourse-appropriate moments
  • gaze cues           held static positions only (raw cues snap — see note)
  • head cues           use with caution (see note)
```

### Gaze cue caveat

Raw `gaze` cues call `SetParameterValue` with no interpolation — the eye jumps instantly. **Use gaze cues only for held static positions.** For smooth gaze transitions, use the `look_away` reaction clip, which animates `ParamEyeBallX/Y` via smooth keyframe curves.

### Head cue caveat

`head` cues write to `AngleX/Y/Z` directly, then `CubismBreath` runs on the same parameters in the same update tick. Whether breath overwrites or blends with cue values is **unverified** pending the majo cue conflict test. Until resolved, prefer reaction clips for head movement over raw head cues.

---

## Compliance Tiers

| Tier | Meaning |
|---|---|
| **Mandatory** | Required for spec compliance. Model will fail onboarding without these. |
| **Threshold** | Required for NPC realism threshold. Absence reads as "cheap web avatar." |
| **Enhancement** | Optional. Adds richness; not required. |

**Minimum to pass spec:** 4 mandatory expressions + idle + 3 threshold reactions.
**Threshold set:** mandatory + sad + angry expressions.

---

## Expressions

Expressions are authored as `.exp3.json` files. The renderer blends to them smoothly using `CubismExpressionMotionManager`. Every expression **must** set parameters across all three facial regions (brows, eyes, mouth).

**File requirements for all expressions:**
- `FadeInTime` ≥ 0.15 s (zero = snap — immediately visible as wrong)
- `FadeOutTime` ≥ 0.3 s
- Non-zero deltas in all three regions

### neutral — Mandatory

> Resting default state. Calm and composed.

**When to use:** Scene start, pauses, topic transitions, any moment without strong emotional valence. Always emit `neutral` at `t=0`. Return to neutral after strong expressions unless the next line continues the same emotion.

| Region | Target |
|---|---|
| Brow | Resting / level |
| Eye | Resting openness (~0.9) |
| Mouth | Flat or slight upward curve |

**Cue:** `{ "time": 0.0, "emotion": "neutral" }`

> **Video:** _TODO — add example clip once majo neutral expression is verified._

---

### happy — Mandatory

> Warm positive emotion. Elevated joy.

**When to use:** Good news, laughter, warm moments, affirmation, sharing something exciting.

| Region | Target |
|---|---|
| Brow | Raised |
| Eye | Squint / Duchenne marker (eyes smile) |
| Mouth | Upward curve |

**Cue:** `{ "time": 1.2, "emotion": "happy" }`

> **Video:** _TODO — add example clip once majo happy expression is verified._

---

### serious — Mandatory

> Focus or emphasis. Not angry — deliberate concentration or gravity.

**When to use:** Important points, warnings, instructions, moments requiring authority or weight.

| Region | Target |
|---|---|
| Brow | Lowered (purposeful, not hostile) |
| Eye | Slight reduction in openness |
| Mouth | Flat or slight downward |

**Cue:** `{ "time": 2.0, "emotion": "serious" }`

> **Video:** _TODO — add example clip once majo serious expression is authored and verified._

**Note:** `serious` must be authored as a new `.exp3.json` for majo. It does not yet exist.

---

### surprised — Mandatory

> Shock or astonishment.

**When to use:** Unexpected reveals, sudden facts, startled reactions.

| Region | Target |
|---|---|
| Brow | Raised high |
| Eye | Widened |
| Mouth | Slight open |

**Cue:** `{ "time": 3.5, "emotion": "surprised" }`

> **Video:** _TODO — add example clip once majo surprised expression is verified._

---

### sad — Threshold

> Disappointment, empathy, or somber tone.

**When to use:** Bad news, losses, empathetic listening, regret.

| Region | Target |
|---|---|
| Brow | Arched inward (worried shape) |
| Eye | Softened / reduced openness |
| Mouth | Downturned |

**Cue:** `{ "time": 4.0, "emotion": "sad" }`

> **Video:** _TODO — add example clip once majo sad expression is verified._

---

### angry — Threshold

> Frustration, irritation, or confrontation. Strong negative emotion.

**When to use:** Injustice, strong disagreement, frustration with a situation. Avoid directing this at the viewer.

| Region | Target |
|---|---|
| Brow | Furrowed down |
| Eye | Narrowed |
| Mouth | Tight downturned or open with tension |

**Cue:** `{ "time": 5.0, "emotion": "angry" }`

> **Video:** _TODO — add example clip once majo angry expression is verified._

---

### bored — Enhancement

> Disengagement or mild disdain.

**When to use:** Sarcasm, impatience, obvious statements, comedic deflation.

| Region | Target |
|---|---|
| Brow | Flat / heavy |
| Eye | Heavy-lidded (~0.5 openness) |
| Mouth | Flat |

**Cue:** `{ "time": 1.0, "emotion": "bored" }`

> **Video:** _TODO — add example clip once majo bored expression is verified._

---

### curious — Enhancement

> Mild interest or attentiveness. Lighter than surprised.

**When to use:** Listening beats, gentle reactions, rhetorical questions.

| Region | Target |
|---|---|
| Brow | One or both slightly raised |
| Eye | Normal openness |
| Mouth | Slight corner lift |

**Cue:** `{ "time": 1.0, "emotion": "curious" }`

> **Video:** _TODO — add example clip once majo curious expression is authored and verified._

---

### embarrassed — Enhancement

> Flustered or self-conscious.

**When to use:** Compliments, self-deprecating moments, awkward situations.

| Region | Target |
|---|---|
| Brow | Raised |
| Eye | Averted / partially closed |
| Mouth | Strained smile |

**Cue:** `{ "time": 1.0, "emotion": "embarrassed" }`

> **Video:** _TODO — add example clip once majo embarrassed expression is authored and verified._

---

## Reactions

Reactions are motion clips (`.motion3.json`). They play once and the model returns to idle. Parameter names **must** come from the model's own `.cdi3.json` — never copied from another model.

**File requirements for all reactions:**
- `FadeInTime` ≥ 0.1 s
- `FadeOutTime` ≥ 0.1 s

### idle — Mandatory

> Default ambient loop. Breathing, sway, subtle head drift, ambient gaze variation.

**Managed by the renderer** — do not emit `idle` cues. The renderer restarts idle automatically when no higher-priority motion is playing.

The idle motion must:
- Produce visible head movement (not a frozen hold)
- Cover at least `ParamAngleX` and `ParamAngleZ` with non-trivial amplitude
- Be ≥ 3 s before looping
- Include `ParamEyeBallX/Y` keyframes for ambient gaze drift (slight variation away from center)

> **Video:** _TODO — add idle loop clip once majo idle motion quality is verified._

---

### nod — Threshold

> Discourse acknowledgement. Head dips and returns. Signals agreement or sentence completion.

**When to use:** Sentence boundaries, affirmations, agreement beats, listening acknowledgements. This is the highest-ROI single reaction — it alone fixes the "reciting" feel.

**Duration:** ~0.5 s
**Key parameters:** `ParamAngleX` — dip –10 to –15° and return.

**Cue:** `{ "time": 3.5, "reaction": "nod" }`

> **Video:** _TODO — add example clip once majo nod motion is authored and approved._

---

### look_away — Threshold

> Deliberate gaze break. Eyes move off-camera, head follows. Conveys thinking or recalling.

**When to use:** "Let me think…" moments, recall pauses, rhetorical questions, internal reflection beats.

**Duration:** ~1.5 s
**Key parameters:** `ParamEyeBallX/Y` on smooth keyframe curves; `ParamAngleY` head follow offset ~150 ms behind eye movement, ~30–40% of eye deflection amplitude.

**Cue:** `{ "time": 5.0, "reaction": "look_away" }`

**Important:** This must use smooth keyframe curves — not a raw `gaze` cue. A raw gaze cue would snap. If the rendered clip shows a smooth arc on the eye movement, gaze capability is confirmed.

> **Video:** _TODO — add example clip once majo look_away motion is authored and approved._

---

### tap — Threshold

> Startled jolt with recovery. Reaction to an unexpected interruption or touch.

**When to use:** Sudden topic changes, startled reactions, comedic timing beats.

**Duration:** ~1.0 s
**Key parameters:** `ParamAngleZ` — jolt and recovery.

**Cue:** `{ "time": 7.0, "reaction": "tap" }`

> **Video:** _TODO — add example clip once majo tap motion is authored and approved._

---

### shake — Enhancement

> Negative head shake. Two-cycle left-right. Signals disagreement or refusal.

**When to use:** Disagreement, corrections, "no" responses, refusal.

**Duration:** ~0.8 s
**Key parameters:** `ParamAngleZ` ±10–15°, two cycles.

**Cue:** `{ "time": 2.0, "reaction": "shake" }`

> **Video:** _TODO — add example clip once majo shake motion is authored and approved._

---

## Usage Guidelines for AvatarCueAgent

- Always open with `{ "time": 0.0, "emotion": "neutral" }`.
- Return to `neutral` after strong expressions (sad, angry, surprised) unless the next line continues the same emotion.
- Inject `nod` at natural sentence boundaries — not mid-sentence.
- Inject `look_away` at genuine recall/thinking pauses — do not overuse.
- Do not stack reactions. Wait for the previous reaction duration to elapse before triggering another.
- Use raw `gaze` cues only for held static positions (e.g. consistently looking at an off-screen object). Never for transitions.
- Do not emit `idle` cues — the renderer manages idle restart automatically.
- Check `assets/models/registry.json` at pipeline start to confirm available expressions and reactions for the target model before generating cues.

---

## Versioning

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-03-17 | Initial spec: 4 mandatory + 2 threshold expressions; idle + 3 threshold reactions; gaze via upstream cues only. |

Breaking changes (removing required behaviours, changing minimum counts) bump the major version.
Additive changes (new optional behaviour types) do not.

When the spec version changes, `model-onboarding.md` and `registry.json` schema must be updated in the same PR.
