# Majo Behaviour Authoring — Handover

**Last updated:** 2026-03-18
**Spec:** `live2d/docs/agent-team-spec.md` (Phases A2–D2)
**Workflow reference:** `live2d/spec/v1/behaviour-authoring-workflow.md`

---

## Status: COMPLETE

All mandatory and threshold behaviours per Avatar Behaviour Spec v1 are approved.
Open items below are non-blocking enhancements deferred to Phase D or later.

---

## Phase C5 — Registry update + spec compliance (2026-03-18)

Round 3 approved all three reaction clips. Registry updated with 8 emotions and 4 approved reactions.
Spec compliance check written to `review_log/compliance_check.md`.

**Compliance result: PASS** — majo meets Avatar Behaviour Spec v1 mandatory + threshold minimums.

| Category | Result | Note |
|---|---|---|
| Expressions — mandatory | Pass | neutral, happy, surprised present; angry proxies for serious/emphasis |
| Expressions — threshold | Pass | sad + angry both approved |
| Reactions — mandatory | Pass | idle approved round 1 |
| Reactions — threshold | Pass | nod, look_away, tap all approved round 3 |

**One spec gap noted (non-blocking):** No dedicated `serious`/emphasis expression. `angry` serves as proxy; a standalone `serious` expression is recommended as a future enhancement.

### Open items (non-blocking)

| Item | Severity | Next action |
|---|---|---|
| `serious`/emphasis expression | Minor | Author dedicated expression post-Phase-D if desired |
| `embarrassed` blush mechanism | Cosmetic | Investigate shiori blush transposition (separate art task) |
| `shake` reaction | Enhancement/optional | Not authored; not required for spec threshold |
| Workflow doc finalisation | Process | Phase D1 — update `spec/v1/behaviour-authoring-workflow.md` with majo lessons learned |
| Workflow doc human sign-off | Process | Phase D2 — human review and approval of workflow doc |

---

## Completed work

### Phase A — Documentation
- `spec/v1/behaviour-authoring-workflow.md` — full behaviour authoring workflow (Phases 0–6), including required render annotation rules (explanatory header + per-frame timestamp on every review render).

### Phase B — Audit + asset authoring

| Item | Output |
|------|--------|
| B1 pre-authoring audit | `assets/models/majo/audit.md` |
| B2 expression fade fixes | All 8 `.exp3.json` — added `FadeInTime: 0.2`, `FadeOutTime: 0.4` |
| B3 head cue conflict test | `tests/fixtures/majo_cue_test_annotated.mp4` — **head_cues_reliable = true** |
| B4 idle gaze drift | `Scene1.motion3.json` — added `ParamEyeBallX/Y` keyframe curves |
| B5 reaction clips | `motions/nod.motion3.json`, `look_away.motion3.json`, `tap.motion3.json` |

### Phase C — Review loop
- Round 1 full review render + SDK bug fixes (two SIGSEGV bugs resolved — see SDK bugs section)
- Round 2 targeted re-renders: expressions (curious, embarrassed approved); reactions diagnosed (nod, look_away, tap marked Revise)
- Round 3 targeted re-renders: nod, look_away, tap all Approved
- `review_log/round_1.json`, `review_log/round_2.json`, `review_log/round_3.json`
- Phase C5: registry updated (8 emotions, 4 reactions); spec compliance check → `review_log/compliance_check.md`

---

## Expression status

| Expression | Status | Notes |
|------------|--------|-------|
| `neutral` | Approved | |
| `happy` | Approved | |
| `surprised` | Approved | |
| `sad` | Approved | |
| `angry` | Approved | |
| `bored` | Approved | |
| `curious` | Approved | Added eye widening (`ParamEyeLOpen/R: 1.05 Multiply`), fixed brow direction. Backups: `curious_v0`, `curious_v1` |
| `embarrassed` | Approved | Expression itself approved round 2. Blush mechanism not accessible via `.exp3.json` — blush investigation deferred (non-blocking). |

---

## Reaction clip status

### idle (Scene1.motion3.json) — Approved
Added `ParamEyeBallX` and `ParamEyeBallY` gaze drift curves. Backup: `Scene1_v0.motion3.json`.

### nod — Approved (round 3)

Final shape: neutral → rise (+5, t=0.22s) → dip (−10, t=0.40s) → ease (−3, t=0.55s) → return (0, t=0.70s)
FadeOutTime: 0.6s. Entry-dependent (ParamAngleX ±5°, implicit out-of-range mode).

| Version | File | Change |
|---------|------|--------|
| v0 | `nod_v0` | Initial: `ParamAngleX=−10`, Linear, 0.5s — wrong axis (AngleX=yaw not pitch) |
| v1 | `nod_v1` | Reduced to −7; added AngleY/Z hold curves |
| v2 | `nod_v2` | Remapped to `ParamAngleY` (confirmed pitch axis) |
| v3 | `nod_v3` | Confirmed by calibration render — AngleY=−10 = downward head dip |
| v4 (active) | `nod` | Up-then-down shape; peak reduced from −22 to −10 (round 3 fix); FadeOutTime 0.6s |

### look_away — Approved (round 3)
- Eyes drift right/up, head follows after 150ms, hold, return
- FadeOutTime increased from 0.4 → 0.6s (round 3 fix)
- Backups: `look_away_v0`, `look_away_v1`

### tap — Approved (round 3)
- `ParamAngleZ` damped oscillation (roll jolt); `ParamAngleX` micro-jolt (chin-up on impact)
- FadeOutTime increased from 0.3 → 0.5s (round 3 fix)
- Backups: `tap_v0`, `tap_v1`

---

## BLOCKING RENDERER BUG

**File:** `src/render/live2d_model.cpp`, `Update()` method

### What happens

A save/restore guard prevents CubismBreath from overwriting angle parameters while a
reaction motion is playing (priority 2):

```cpp
bool reactionActive = (_motionManager->GetCurrentPriority() >= 2);
if (reactionActive) { /* save AngleX, AngleY, AngleZ */ }
if (_breath) _breath->UpdateParameters(_model, deltaTime);
if (reactionActive) { /* restore saved values */ }
```

When the reaction motion finishes, `IsFinished()` triggers `StartMotionPriority(idle, false, 1)`,
dropping priority to 1 on the same frame. `reactionActive` immediately evaluates false.
Breath runs unsuppressed and snaps to its current sinusoidal phase — mid-fade.

### Fix (Option A — preferred)

Read the reaction motion's fade weight and blend breath back proportionally:

```cpp
float reactionWeight = /* get fade weight from motion manager */;
// After running breath:
// lerp(breath_output, saved_value, reactionWeight)
// so breath fades IN gradually as the reaction fades OUT
```

If `CubismMotionManager` doesn't expose a fade weight accessor, track it manually:
set a `_reactionFadeWeight` member to 1.0 when a reaction starts, then decrease it
by `deltaTime / FadeOutTime` each frame after `IsFinished()` returns true.

### Current correct update order (do not change this structure)

```
LoadParameters
→ UpdateMotion (idle priority 1 or reaction priority 2)
→ SaveParameters        ← anchor; breath must NOT be included here
→ ExpressionManager
→ Cue params (guarded: only when priority < 2)
→ Mouth/lipsync
→ [save AngleX/Y/Z if reactionActive]
→ CubismBreath::UpdateParameters
→ [restore AngleX/Y/Z if reactionActive]   ← snap happens here on priority drop
→ Physics / Pose
→ Model->Update()
```

---

## Confirmed axis meanings (majo model)

Confirmed by visual calibration renders.

| Parameter | Axis | Sign |
|-----------|------|------|
| `ParamAngleX` | Left/right yaw | + = turn right |
| `ParamAngleY` | Up/down pitch | + = look up, − = look down / nod dip |
| `ParamAngleZ` | Tilt/roll | + = lean right |
| `ParamEyeBallX` | Gaze horizontal | + = right |
| `ParamEyeBallY` | Gaze vertical | + = up |

CubismBreath amplitudes: AngleX ±15° (yaw), AngleY ±8° (pitch), AngleZ ±10° (roll), BodyAngleX ±4°.

---

## SDK bugs fixed in this session

### 1. JSON parser space-before-brace SIGSEGV
Single-line motion JSON (`{ "File": "...", "FadeOutTime": 0.3 }`) caused crash.
Parser `CubismJson::ParseNumeric` doesn't recognise space as a numeric terminator.
**Fix:** expand all motion entries to multi-line format in `majo.model3.json`.

### 2. Multiple motions per group SIGSEGV
Multiple motions under one group key crashed the SDK.
**Fix:** one motion per group — `"Nod"`, `"LookAway"`, `"Tap"` separate groups.

### 3. Cue sequencer overwriting motion keyframes
Cue sequencer unconditionally wrote `SetParameterValue` for angle params after `UpdateMotion`.
**Fix:** guard cue writes: `if (_motionManager->GetCurrentPriority() < 2)`.

### 4. Breath accumulation (introduced and fixed)
Moving breath before `SaveParameters` caused per-frame accumulation.
**Fix:** breath after `SaveParameters`; binary save/restore guard.

---

## Remaining work (Phase D)

Phase C is complete. Remaining items:

1. **Phase D1** — Update `spec/v1/behaviour-authoring-workflow.md` with majo lessons learned:
   - CubismBreath snap at reaction end (known limitation, documented; FadeOutTime mitigation)
   - round_3.json process notes (axis label error in round_2 diagnosis, actual file values differed from proposed fix values)
   - Entry validation review workflow (`majo_nod_nocheck` registry entry pattern)
2. **Phase D2** — Human sign-off on workflow doc
3. **Enhancement (optional):** Author `serious`/emphasis expression to close spec gap
4. **Enhancement (optional):** Investigate blush mechanism for `embarrassed` (shiori transposition)

---

## Key file paths

| Asset | Path |
|-------|------|
| This handover | `assets/models/majo/HANDOVER.md` |
| Audit | `assets/models/majo/audit.md` |
| Expressions | `assets/models/majo/expressions/` |
| Idle motion | `assets/models/majo/Scene1.motion3.json` |
| Reaction clips | `assets/models/majo/motions/` |
| Motion notes | `assets/models/majo/motions/README.md` |
| Review logs | `assets/models/majo/review_log/` |
| Model registry | `assets/models/registry.json` |
| Renderer | `src/render/live2d_model.cpp` |
| Workflow spec | `spec/v1/behaviour-authoring-workflow.md` |
| Latest nod render | `tests/fixtures/majo_review/calibration_nod_v4.mp4` |
