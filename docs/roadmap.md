# Live2D Feature Expansion Roadmap

**Date:** 2026-03-17
**Status:** Active — research complete, renderer audit complete, writing spec

---

## Problem Statement

The current renderer accepts expression and reaction cues from a scene manifest but the
behaviour vocabulary is shallow:

- **Majo** (primary target): 6 emotions, 1 reaction (`idle` only). No motion clips for
  `nod`, `shake`, `look_away`, `blink`, `tap`, etc.
- **Motion clips** are referenced in the API contract but do not yet exist as authored
  `.motion3.json` files for any VTubeStudio-origin model.
- **Gaze and head cues** are accepted by the manifest schema but are untested.
- **The behaviour spec itself** is undefined — we do not yet have a principled answer to
  "what set of behaviours is sufficient for a believable avatar?"

The core challenge for VTubeStudio-origin models (majo and any future models built for
real-time face tracking) is that no motion clips or extended expressions exist — they must
be **authored from scratch**, requiring an iterative agent + human review loop.

Coverage gaps in other registered models (shiori, haru, hiyori, etc.) are **out of scope**
for this roadmap. Focus is exclusively on majo and the workflow/spec that will govern all
future model additions.

---

## Goals

1. **NPC Realism Threshold Research** — determine the minimal set of behaviours required
   for an avatar to read as "AAA NPC quality" (not a real human, but not visibly broken or
   cheap). This research output becomes the basis for the spec.

2. **Avatar Behaviour Spec v1** — a canonical, versioned list of behaviours every registered
   model must support, derived from Goal 1. New models are held to this spec during onboarding.

3. **Claude Workflow Document** — a step-by-step guide for an agent to author behaviours for
   a new model, interact with the human review loop, and converge on approval.

4. **Majo — Fully Built to Spec** — the majo avatar is used as the reference walkthrough of
   Goal 3, producing a complete, approved behaviour set.

---

## Deliverable 0: NPC Realism Research

**Status:** ✅ Complete — findings reviewed and approved.

Defined threshold: **obviously not a real human piloting the avatar, but could pass as an
NPC from a modern AAA game** (Cyberpunk 2077, BG3, modern JRPG cutscene quality).

Key framing: 2D stylized characters sit outside the uncanny valley entirely. The failure
mode is not "looks almost human but wrong" — it is "looks like a cheap web avatar." The
threshold is about **animation richness signals**, not realism.

### Approved findings (summarised)

**Hard breakers** — absence immediately reads as wrong:
1. Continuous blinking (dead-eye effect within 3–5 s)
2. Lipsync temporal accuracy (<80 ms sync error)
3. Ambient head motion (never completely still — ventriloquist dummy effect)
4. Multi-region facial expressions — eyes+brows+mouth together (Duchenne marker; brows/eyes carry 60–70% of emotional signal)
5. Expression cross-fade blending (no snaps — animatic quality)
6. ~~Hair physics~~ — **skipped** (out of scope for this roadmap)

**High-value threshold** — absence reads as "cheap":
7. Breathing cycle + body sway
8. Discourse-coupled head nod (highest ROI single reaction; fixes "reciting" feel)
9. Gaze variation — not camera-locked (perceived internal life)
10. Emphasis head tilt (speech-body synchrony)
11. Procedural idle randomisation (prevents detectable loop seam, critical for >30 s clips)

**Nice-to-have** (not required for threshold): micro-expression flashes, gaze–head
coupling, extended expression vocabulary, blink variability.

### Renderer audit findings (cross-referenced against research)

A source audit of the renderer revealed that several hard breakers and threshold
behaviours are **already implemented in the renderer** — no additional authoring needed:

| Behaviour | Research priority | Renderer status |
|---|---|---|
| Auto-blinking | Hard breaker #1 | ✅ `CubismEyeBlink` — always active when model has EyeBlink group |
| Lipsync accuracy | Hard breaker #2 | ✅ Rhubarb pipeline already in place upstream |
| Ambient head drift | Hard breaker #3 | ✅ `CubismBreath` drives `AngleX/Y/Z/BodyAngleX` sinusoidally every frame |
| Expression cross-fade | Hard breaker #5 | ✅ `CubismExpressionMotionManager` — fade timing read from `.exp3.json` files |
| Breathing / body sway | Threshold #7 | ✅ `CubismBreath` covers this simultaneously with head drift |
| Idle loop | Foundation | ✅ Auto-restarts `Idle_0` whenever no other motion running |
| Gaze variation | Threshold #9 | ⚠️ Cue-driven gaze works but snaps — smooth gaze must come from motion clips or idle keyframes |
| Head cue vs. Breath | Risk | ⚠️ Head cues write AngleX/Y/Z then CubismBreath runs on same params — interaction unverified |

**Implication:** the renderer already crosses hard breakers 1, 3, 5, and 7 automatically
for any correctly configured model. The remaining work is almost entirely **authoring**
(motion clips, expression file hygiene) rather than renderer changes.

---

## Deliverable 1: Avatar Behaviour Spec v1

**File:** `spec/v1/avatar-behaviour-spec.md` (human-facing) + `spec/v1/avatar-behaviour-spec.json` (machine-readable)
**Status:** ✅ Complete — spec written; example manifests in `spec/v1/behaviour-examples/`. Video clips marked TODO pending majo authoring.

### Spec architecture — three layers

The spec distinguishes what must be **authored** from what is already **provided by the
renderer**, and what must be **driven from upstream** (the scene manifest).

```
Layer 1 — Renderer (already implemented, no per-model work needed)
  • Auto-blinking       — CubismEyeBlink, fires every ~3–6 s
  • Ambient head drift  — CubismBreath on AngleX/Y/Z/BodyAngleX
  • Breathing / sway    — same CubismBreath instance
  • Expression fade     — CubismExpressionMotionManager (timing from .exp3.json)
  • Idle loop           — auto-restarts Idle_0 continuously

Layer 2 — Authored assets (per-model, agent-authored, human-reviewed, tested in this repo)
  • Expression files    — .exp3.json with correct parameter coverage + non-zero fade times
  • Idle motion         — includes ambient gaze drift (ParamEyeBallX/Y keyframes)
  • Reaction clips      — nod, look_away (smooth gaze + head), tap (threshold); shake (enhancement)
  • Gaze capability     — verified via test renders in this repo before upstream integration

Layer 3 — Upstream / manifest (video_agent drives via scene cues; timing only, not mechanism)
  • Discourse nods      — inject reaction:"nod" cues at sentence boundaries
  • Explicit look-away  — inject reaction:"look_away" cues at recall/thinking moments
  • Emotion changes     — inject emotion cues at script-appropriate moments
  • Static gaze lock    — inject gaze cues for exact held positions (snaps; use sparingly)
```

**Critical constraint — gaze and head cues snap:**
Gaze (`ParamEyeBallX/Y`) and head angle cues are applied via `SetParameterValue` with no
interpolation — the eye/head jumps instantly to the requested position. This makes raw cues
unsuitable for smooth gaze transitions. **Smooth gaze movement must come from motion clips**
(the motion system uses proper curve interpolation). Specifically:
- Ambient gaze drift → keyframed in the idle motion
- Deliberate look-away → `look_away` reaction clip animates `ParamEyeBallX/Y` smoothly
- Static gaze hold → raw `gaze` cue (acceptable for held positions)

**Known risk — head cues vs. CubismBreath conflict:**
Head cues write to `AngleX/Y/Z` directly, then CubismBreath runs on the same parameters
in the same update tick. The interaction is unverified — breath may overwrite cue values
or produce unintended blending. This must be tested before head cues are relied upon.
(Reaction clips avoid this issue entirely since they go through the motion priority system.)

### Layer 2 spec — what must be authored for every model

#### Expressions

Every registered model must have a minimum facial expression vocabulary covering these
semantic categories, implemented as `.exp3.json` files. Each expression **must** set
parameters across all three facial regions (brows, eyes, mouth) — not just the mouth.

| Semantic label | Required | Brow movement | Eye movement | Mouth movement |
|---|---|---|---|---|
| `neutral` | ✅ Mandatory | Resting/level | Resting openness (~0.9) | Flat or slight upward curve |
| `happy` / warm | ✅ Mandatory | Raised | Squint (Duchenne) | Upward curve |
| `serious` / emphasis | ✅ Mandatory | Lowered (not angry) | Slight reduction in openness | Flat or slight downward |
| `surprised` | ✅ Mandatory | Raised | Widened | Slight open |
| `sad` | Threshold | Arched inward | Softened / reduced | Downturned |
| `angry` | Threshold | Furrowed down | Narrowed | Tight downturned |
| `bored` | Enhancement | Flat/heavy | Heavy-lidded | Flat |
| `curious` | Enhancement | One or both slightly raised | Normal | Slight corner lift |
| `embarrassed` | Enhancement | Raised | Averted / partially closed | Strained smile |

Minimum to pass spec: the 4 mandatory labels. Threshold: mandatory + sad + angry.

**Expression file requirements:**
- `FadeInTime` ≥ 0.15 s on every `.exp3.json` (engine reads this; zero = snap)
- `FadeOutTime` ≥ 0.3 s on every `.exp3.json`
- All three facial regions (brows, eyes, mouth) must have non-zero parameter deltas

#### Reactions (motion clips)

| Label | Semantic intent | Key parameters | Duration | Tier |
|---|---|---|---|---|
| `idle` | Default loop — breathing, sway, head drift | `AngleX/Y/Z`, `BodyAngleX` | Loops | Mandatory |
| `nod` | Discourse acknowledgement; sentence completion | `ParamAngleX` dip –10 to –15° and return | ~0.5 s | Threshold |
| `look_away` | Thinking / recalling; breaks camera lock | `ParamEyeBallX/Y` + `ParamAngleY` offset, return | ~1.5 s | Threshold |
| `tap` | Startled / interaction reaction | `ParamAngleZ` jolt + recovery | ~1.0 s | Threshold |
| `shake` | Disagreement / no | `ParamAngleZ` ±10–15° two-cycle | ~0.8 s | Enhancement |

Minimum to pass spec: `idle` + the 3 threshold reactions.

**Motion file requirements:**
- `FadeInTime` ≥ 0.1 s, `FadeOutTime` ≥ 0.1 s on all motion files
- All parameter names must be derived from the model's `.cdi3.json` — never copied from another model

#### Idle motion quality floor

The idle motion (`Idle_0`) must:
- Produce visible head movement across its duration (not a frozen hold)
- Cover at least `ParamAngleX` and `ParamAngleZ` with non-trivial amplitude
- Duration ≥ 3 s before looping (the CubismBreath layer adds drift on top)

Note: CubismBreath already adds sinusoidal drift on top of whatever the idle motion does.
The idle motion need not do heavy lifting on head movement — but it must not fight the
breath layer by holding a fixed target.

### Spec versioning

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-03-17 | Initial spec: 4 mandatory + 2 threshold expressions; 4 reactions (idle + 3); gaze via upstream |

When the spec changes, `model-onboarding.md` and `registry.json` schema must be updated
in the same PR. Breaking changes (removing a required behaviour, changing minimum counts)
bump the major version. Additive changes (new optional behaviour types) do not.

---

## Deliverable 2: Claude Workflow for Behaviour Authoring

**File:** `spec/v1/behaviour-authoring-workflow.md` (new)
**Status:** Structure defined here; full document written after Deliverable 1 spec is finalised.

### Overview

This workflow applies whenever a model needs behaviours authored from scratch (no existing
motion clips or expression files) — typically VTubeStudio-origin models. It is a cycle of:
**agent proposes → renders review video → human reviews → agent refines → repeat.**

### Phase 0 — Prerequisites

1. Model passes Stage 1 of `model-onboarding.md` (including VTubeStudio Export Detour if needed, which produces the initial expression set).
2. Expressions are authored and Stage 3 human-approved (emotion mapping complete in registry).
3. Renderer binary is built and confirmed working on at least one test render.
4. Agent reads the model's `.cdi3.json` to enumerate all available parameter IDs before
   authoring anything. This is the parameter budget — nothing outside it can be used.

### Phase 0.5 — Pre-authoring audit (agent)

Before authoring anything, the agent checks what Layer 2 assets already exist or need
fixing — avoiding unnecessary work:

1. **Expression fade times** — open each `.exp3.json`, confirm `FadeInTime` ≥ 0.15 and
   `FadeOutTime` ≥ 0.3. If any are zero or missing, fix them before the review render.
2. **Expression region coverage** — confirm each expression sets parameters in all three
   regions (brows, eyes, mouth). Flag any that only move the mouth.
3. **Idle motion quality** — open the idle motion file, confirm it covers at least
   `ParamAngleX` and `ParamAngleZ` with visible amplitude. Note whether gaze parameters
   are present.
4. **Existing reaction clips** — list any `.motion3.json` files already in the model dir.
   Identify which spec reactions are genuinely missing vs. just unregistered.

Record findings in `<model_dir>/audit.md` before proceeding to Phase 1.

### Phase 1 — Authoring (agent)

Author only the Layer 2 items that are missing or broken per the Phase 0.5 audit.
**Do not re-author things the renderer already provides** (blinking, breathing, head
drift, expression fade — these come free from the engine for any compliant model).

For each required behaviour:

1. Read the spec item (target label, semantic intent, duration, tier).
2. Read the model's `.cdi3.json` — all parameter names and ranges must come from here.
   Never copy parameter names from another model.
3. Read analogous motions from Cubism SDK sample models (Haru's `TapBody`, `Idle`) as
   **format templates only** — for JSON structure and curve encoding, not parameter values.
4. Make a **best-effort initial estimate** of keyframe values, guided by physical
   plausibility. Document the rationale alongside the file.
5. Write the file to `<model_dir>/motions/<label>.motion3.json` or
   `<model_dir>/expressions/<label>.exp3.json`.
6. Wire it into the model's `.model3.json` under the appropriate `FileReferences` key.
7. Record parameter choices and rationale in `<model_dir>/motions/README.md`.

### Phase 2 — Review Render (agent)

The agent produces a labeled review video. The preferred tool is `scripts/behavior_review.py`
(renders one segment per emotion/reaction, burns text labels via FFmpeg). If the review script
is inadequate for a specific test case (e.g., gaze/head cues, physics verification), the agent
**must design an alternative**: write a one-off test manifest and render it directly via the
renderer binary, then post-process with FFmpeg to annotate the output. Do not block on
script limitations — create new scripts or workflows as needed.

Output target: a labeled video where each behaviour is visually isolated and named, making
the human review in Phase 3 as fast as possible.

### Phase 3 — Human Review

The human watches the review video and gives **verbal or written feedback in plain English**.
The agent is responsible for interpreting that feedback and translating it into the structured
feedback record below. The human does not fill out any schema.

**Agent instructions for interpreting human feedback:**

After receiving human feedback, the agent must:
1. Re-read the review video manifest to recall which clip is which.
2. For each clip the human mentioned, determine the verdict (Approved / Revise / Drop) from
   context. Ambiguous phrasing ("that looks a bit off") → Revise. No mention → treat as
   Approved only if the human explicitly said "everything else looks good."
3. For "Revise" clips: identify the specific parameter or timing that needs changing. If the
   human's description is a visual observation ("the nod goes too deep"), map it to a parameter
   (`ParamAngleY` magnitude too large). If genuinely ambiguous, ask one clarifying question
   before proceeding — do not guess blindly at parameter changes.
4. Populate the feedback record:

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

5. Write this record to `<model_dir>/review_log/round_<N>.json` before making any edits.
   This creates a traceable history of what was changed and why.

All feedback for the current round is collected before the agent starts any revisions.

### Phase 4 — Agent Revision Loop

For each clip with `"verdict": "Revise"` in the round log:
1. Apply the `proposed_fix` to the `.motion3.json` or `.exp3.json`.
2. Save the previous version as `<filename>_v<N-1>.json` alongside the new file — do not
   overwrite-only. This allows rollback if the revision makes things worse.
3. Re-render **only the affected clips** (write a targeted manifest with only those cues,
   not the full set) and produce a short labeled video for each changed clip.
4. Human reviews only the changed clips.
5. Agent records the new round in `round_<N+1>.json`.
6. Repeat until `"verdict": "Approved"` or `"verdict": "Drop"`.

**Stopping rule:** if the same clip has been revised ≥ 3 times with no approval, the agent
must explicitly ask the human: "Should I continue iterating, or drop this behaviour?"

### Phase 5 — Registry Update (agent)

Once all behaviours are resolved (approved or dropped with documented reason):
1. Update `registry.json` with new `emotions` and `reactions` entries for approved items.
2. For any dropped items, add a `"gaps"` field to the registry entry documenting what was
   dropped and why (e.g., parameter budget too limited, indistinct from another expression).
3. Run the full test fixture suite to confirm no regressions.

### Phase 6 — Spec Compliance Check (agent)

Verify the model meets Avatar Behaviour Spec v1 (from Deliverable 1):
- Check each hard-breaker behaviour is present and approved.
- Check threshold behaviours meet the minimum counts from the spec.
- Document any gaps vs. the spec in the registry entry.

If minimums are not met, iterate further or escalate to the human with a clear statement:
"This model cannot meet spec minimum X because [reason]. Options: [A] continue iteration,
[B] accept as a limited model with documented gap, [C] reject model."

---

## Deliverable 3: Majo — Full Spec Build

**Goal:** Walk majo through Deliverable 2 workflow and produce an approved, spec-complete
behaviour set. This is both the product (a usable avatar) and the proof-of-concept for
the workflow.

### Current state (majo)

| Category | Status | Spec requirement | Gap |
|---|---|---|---|
| Auto-blinking | ✅ Renderer handles | Hard breaker | None |
| Breathing + head drift | ✅ Renderer handles | Hard breaker | None |
| Expression cross-fade | ⚠️ Engine handles, but fade times in files unverified | Hard breaker | Audit needed |
| Emotions | 6 approved: `neutral`, `happy`, `surprised`, `bored`, `sad`, `angry` | 4 mandatory + 2 threshold = 6 | Meets threshold; `curious`/`embarrassed` are enhancements |
| Reactions — `idle` | ✅ Exists (`Scene1.motion3.json`) | Mandatory | Quality TBD (audit needed) |
| Reactions — `nod` | ❌ Missing | Threshold | Must author |
| Reactions — `look_away` | ❌ Missing | Threshold | Must author |
| Reactions — `tap` | ❌ Missing | Threshold | Must author |
| Reactions — `shake` | ❌ Missing | Enhancement | Optional |
| Gaze variation (smooth) | ⚠️ Motion clips provide smooth gaze; raw cue snaps | Layer 2 (idle + look_away) | Verified via look_away render |
| Gaze variation (static) | ⚠️ Snap-to-position via cue; untested | Layer 3 | Needs cue test manifest |

### Work items

#### 3.1 Pre-authoring audit

Run Phase 0.5 audit on majo:
- Check `.exp3.json` fade times (6 files)
- Check idle motion (`Scene1.motion3.json`) for head movement amplitude and parameter coverage
- Check whether gaze parameters appear in the idle motion

Expected output: `assets/models/majo/audit.md`

#### 3.2 Expression fade time fixes (if needed)

If audit finds zero or missing `FadeInTime`/`FadeOutTime` in any `.exp3.json`, fix before
the review render. This is a correctness fix, not a creative authoring task — should not
require human review.

#### 3.3 Head cue conflict test (BLOCKING — run before 3.4)

Write `tests/fixtures/majo_cue_test.json` with explicit `head` cues and render it. The
test must produce a visible head position change; if CubismBreath overwrites the cue the
head will remain in its breath-driven position regardless of the cue value.

**Pass**: head moves visibly to the cued angle → head cues are reliable; reaction clips
may use raw head cues as a supplementary mechanism.

**Fail**: head shows no response to cues → raw head cues are broken; all head movement
must be authored into motion clips. Update the spec to note this. Reaction clips should
encode all head movement as keyframe curves — do not rely on head cues for head direction.

Also test `gaze` cues (snap-to-position range/direction), and combined `emotion` +
`reaction` cues to confirm no interference.

#### 3.4 Reaction clip authoring

Author the three threshold reactions. Parameter names must be derived from majo's
`.cdi3.json` — the values below are conceptual starting points only.

| Reaction | Semantic intent | Initial approach | Duration |
|---|---|---|---|
| `nod` | Discourse acknowledgement | `ParamAngleX` dip –10 to –15° and return | ~0.5 s |
| `look_away` | Thinking; breaks camera lock | `ParamEyeBallX/Y` offset on smooth curve; `ParamAngleY` head follow encoded as a second curve with keyframes shifted ~150 ms later and amplitude ~30–40% of eye deflection | ~1.5 s |
| `tap` | Startled reaction | `ParamAngleZ` jolt + recovery | ~1.0 s |

`look_away` is the primary gaze capability proof — it must use smooth curve keyframes on
`ParamEyeBallX/Y`, not a snap. If the motion clip produces a visible smooth arc, gaze
capability is confirmed.

`shake` (enhancement) authored only if time permits after threshold reactions are approved.

#### 3.5 Idle motion gaze drift

Verify or add `ParamEyeBallX/Y` keyframes to the idle motion. This provides ambient gaze
variation (slight drift away from center during speech) without any upstream cues. Confirm
in a test render that the eye moves subtly during idle — if it does, ambient gaze is solved.

#### 3.6 Spec compliance sign-off

Run Phase 6 compliance check. Record result in registry entry.

---

## Implementation Sequence

```
Phase 0 — Research                                                  ✅ DONE
  0.1. NPC realism research                                         [agent — complete]
  0.2. Human approves research output                               [human — complete]
  0.3. Renderer audit (what's already built in)                     [agent — complete]

Phase A — Foundation                                                CURRENT
  A1. Write Avatar Behaviour Spec v1 (spec/v1/avatar-behaviour-spec.md)[agent — complete]
  A2. Write Behaviour Authoring Workflow doc                         [agent]
  A3. Confirm renderer binary builds on target machine               [human+agent]

Phase B — Majo Pre-authoring (Deliverable 3.1–3.5)
  B1. Run Phase 0.5 audit on majo (fade times, idle quality, gaze in idle) [agent]
  B2. Fix expression fade times if needed                            [agent]
  B3. Head cue conflict test (majo_cue_test.json)                   [agent+human]
      — send head cues, confirm visible response, verify CubismBreath
        does not overwrite; MUST resolve before authoring reaction clips
      → If head cues work: reaction clips may include head movement
      → If head cues are overwritten: reaction clips are the ONLY head
        movement mechanism; raw head cues marked as unreliable in spec
  B4. Add gaze drift keyframes to idle motion if absent              [agent]
  B5. Author nod, look_away, tap reaction clips                      [agent]
      (look_away must use smooth EyeBall + time-shifted AngleY curves)

Phase C — Majo Review Loop (Deliverable 3.3–3.6)
  C1. Run review render → human review round 1                       [human]
  C2. Agent interprets feedback → populates round_1.json → revises   [agent]
  C3. Human reviews changed clips                                    [human]
  C4. Repeat C2–C3 until all clips resolved                          [loop]
  C5. Registry update + spec compliance check                        [agent]

Phase D — Workflow Document Finalisation
  D1. Update behaviour-authoring-workflow.md with any divergences           ✅ DONE
      discovered during Phases B–C → moved to docs/; 7 lessons added
  D2. Workflow doc reviewed and approved                             [human]

Phase E — Full Integration Fixture (cross-repo)
  BLOCKED ON: Deliverable 3 complete AND video_agent updated to Spec v1

  E0. Update video_agent to generate manifests conforming to Spec v1 [video_agent work]
      — MUST be done before E1; fixture generated with pre-Spec v1
        manifests would silently skip unrecognised cues and appear to pass
  E1. Generate a full fixture: real script → TTS audio → Rhubarb lipsync
      → AvatarCueAgent manifest → render with majo                   [agent+human]
  E2. Verify no cues were silently skipped — check renderer log for
      "Cue … not in model vocabulary — skipped" warnings; any skip is a
      mismatch between video_agent's vocabulary and majo's registry    [agent]
  E3. Human reviews the full rendered output end-to-end              [human]
  E4. Any issues fed back to renderer (bugs) or video_agent (cue generation)
```

---

## Open Questions / Risks

1. **motion3.json format nuances** — The Cubism SDK motion format has non-obvious curve
   types, segment encoding, and `UserData` fields. Mitigation: read Haru's working sample
   motions as format templates before authoring, not after a parse failure.

2. **behavior_review.py gaps** — The script covers expressions and reactions but not
   gaze/head cues. Gaze/head testing uses a separate one-off test manifest (Deliverable
   3.4). Not a blocker — create targeted scripts as needed.

3. **majo curious/embarrassed** — Dropped during initial onboarding. Per spec v1 these
   are "enhancement" tier — not required for threshold compliance. Remain a known gap,
   documented in the registry entry.

4. **Physics overshoot on reaction clips** — majo has a `.physics3.json`. Motion clips
   that look correct in parameter space may overshoot in the render due to physics lag.
   The human review loop is the mechanism for catching this — it will surface in the
   first review render.

5. **Gaze cues snap; smooth gaze requires motion clips** — Raw `gaze` cues in the manifest
   call `SetParameterValue` directly with no interpolation. Eye position jumps instantly.
   Smooth gaze transitions must be authored into motion clips (`look_away`) or the idle
   motion (`ParamEyeBallX/Y` keyframes). Raw gaze cues are only appropriate for held
   static positions. We want to verify this with human review. 

6. **CubismBreath vs. head cues conflict** — Head cues write to `AngleX/Y/Z` then
   CubismBreath runs on the same parameters in the same update tick. Whether breath
   overwrites or blends with cue values is unverified. Phase C5 will surface this.
   If confirmed as a conflict, head movement should be authored exclusively into motion
   clips and raw head cues treated as unreliable.

7. **Linux build** — Renderer targets Linux via OpenGL. D3D11/Windows is not supported.
   Build system: CMake + GCC/Clang.

---

## Deliverable 4: Full Integration Fixture

**Status:** Blocked on Deliverable 3 + video_agent Spec v1 update.

After majo is spec-complete and video_agent is updated to generate Spec v1-conformant
manifests, generate a real end-to-end fixture to prove the entire pipeline works together.

### What this produces

A complete render using real content:
- **Script**: a short (30–60 s) piece of scripted dialogue written for the test
- **TTS audio**: generated via the existing audio pipeline
- **Rhubarb lipsync**: real phoneme timeline from the audio (not the cheesetest template)
- **Manifest**: generated by video_agent's AvatarCueAgent using Spec v1 behaviour vocabulary
  (nod cues at sentence boundaries, look_away at thinking moments, emotion changes from
  script sentiment, gaze cues where appropriate)
- **Render**: majo avatar rendered to MP4

### Purpose

This is the first real-world test of the full loop. It will surface:
- Whether video_agent generates sensible cue timing and density
- Whether the authored majo behaviours hold up in continuous use (not just isolated clips)
- Whether gaze/head cue interactions produce acceptable output in context
- Any missing behaviours that the spec should have required but didn't

The fixture output (`tests/fixtures/spec_v1_integration/`) becomes the canonical
regression test for future spec changes.

---

## Success Criteria

| Deliverable | Done when |
|---|---|
| NPC realism research | ✅ Complete — prioritised behaviour list delivered and human-approved |
| Spec v1 | `spec/v1/avatar-behaviour-spec.md` written, reviewed, referenced from `model-onboarding.md` |
| Workflow doc | `spec/v1/behaviour-authoring-workflow.md` used end-to-end for majo; updated to match what actually happened |
| Majo spec-complete | 4 mandatory + 2 threshold expressions approved; `idle` + 3 threshold reactions approved; head cue conflict resolved; look_away demonstrates smooth gaze; round logs in `majo/review_log/` |
| Full integration fixture | video_agent updated to Spec v1; real script → TTS → Rhubarb → manifest → majo render with zero skipped cues; reviewed end-to-end and approved |
