# CubismBreath Guard — Investigation Findings

## Background

During calibration of the majo reaction animations, we investigated how
`CubismBreath::UpdateParameters` interacts with priority-2 reaction motions.
The investigation used a side-by-side review video
(`tests/fixtures/majo_review/review_breath_snap.mp4`) that rendered the same
nod sequence under three renderer configurations.

---

## The Three Guard Modes

### 1. No guard (breath always runs)

```cpp
if (_breath)
    _breath->UpdateParameters(_model, deltaTime);
```

Breath oscillates continuously on AngleX/Y/Z/BodyAngleX throughout all
motions, including priority-2 reactions.

**Behaviour at reaction exit:** seamless — there is no discontinuity because
breath was never suppressed. The head simply continues from wherever it was.

**Visual quality:** most natural for short reactions (nods, taps). The subtle
oscillation during the motion hold is imperceptible, and the exit is clean.

---

### 2. Binary guard (original buggy code — do not use)

```cpp
if (_motionManager->GetCurrentPriority() < 2 && _breath)
    _breath->UpdateParameters(_model, deltaTime);
```

Breath is fully suppressed while a priority-2 reaction is active. On the
exact frame priority drops to 0, breath runs at its current accumulated
sinusoidal phase with no transition.

**Behaviour at reaction exit:** visible snap. If the motion held the head at
0° for 1+ seconds, the breath timer accumulated phase while frozen. When
released, AngleX can jump ±15° in a single frame.

**Visual quality:** jarring, especially for longer reactions where the phase
diverges far from the freeze point.

---

### 3. Lerp guard (current fix in `fix/breath-snap-renderer`)

```cpp
// During reaction: _reactionFadeWeight = 1.0
// After reaction:  _reactionFadeWeight decays to 0 over 0.5s

if (_reactionFadeWeight > 0.0f) {
    const float savedAngleX = _model->GetParameterValue(_idParamAngleX);
    // ... save all four params
    _breath->UpdateParameters(_model, deltaTime);
    const float w = _reactionFadeWeight;
    _model->SetParameterValue(_idParamAngleX,
        _model->GetParameterValue(_idParamAngleX) * (1.0f - w) + savedAngleX * w);
    // ... lerp all four params back
} else {
    _breath->UpdateParameters(_model, deltaTime);
}
```

Breath is suppressed during the reaction (head frozen at motion position).
After reaction ends, the breath contribution fades in over 0.5s.

**Behaviour at reaction exit:** no snap, but the cue system writes 0° to all
angle params on the first post-reaction frame. The head briefly returns to
centre before breath fades in. For short reactions this is perceptibly
different from the no-guard version.

**Visual quality:** better than binary guard for *long* reactions; marginally
worse than no-guard for short reactions because the "return to centre → fade
in" sequence adds a subtle artificial beat.

---

## Key Insight: Guard Choice Depends on Reaction Duration

| Reaction length | Recommended guard | Reason |
|---|---|---|
| Short (< ~1s): nod, tap | No guard | Breath phase diverges < 10°; exit is seamless |
| Long (> ~2s): hold, look-away, emotion lock | Lerp guard | Phase can diverge ±15°; lerp prevents visible snap |

A practical threshold is whether the reaction motion's `Duration` exceeds
roughly 1.5s. Below that, removing the guard entirely produces the most
natural result.

---

## What "Natural" Means Here

The no-guard version feels natural because the model is *always alive* — the
subtle breath oscillation never pauses. A human performer does not stop
breathing during a head nod; the breath continues underneath.

The lerp guard models a different intent: that certain reactions (long holds,
precise emotional states) need the head to be locked on the motion's keyframes
without interference from breath. The trade-off is a freeze-then-fade that
can feel slightly robotic on short reactions.

---

## Recommended Next Step

Consider making the guard mode a per-reaction property, or implement a
duration-based heuristic in `TriggerMotion`:

```cpp
// Pseudo-code: only activate lerp guard for long reactions
float duration = motion->GetDuration();
_useBreathGuard = (duration > 1.5f);
```

This would give short reactions (nod, tap) the seamless no-guard behaviour
and long reactions the snap-prevention lerp guard.

---

## Review Artefacts

- `tests/fixtures/majo_review/review_breath_snap.mp4` — 18s comparison clip.
  - Clip 1 (0–9s): no-guard renderer. Two nods at t=2.0s and t=4.0s.
    Second nod exits at t≈4.9s when `ParamAngleX` breath is near peak
    (−15°). Head tilts sideways immediately after nod exit.
  - Clip 2 (9–18s): lerp-guard renderer. Same nods. Head stays centred at
    nod exit; breath fades in over 0.5s.
- `assets/models/majo/motions/nod_review.motion3.json` — 0.9s review motion
  (0.3s descent to −15°, 0.2s hold, 0.4s return to 0°, FadeOutTime=0).
  Designed so the second nod aligns breath phase with AngleX amplitude peak.
