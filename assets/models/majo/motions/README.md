# majo Reaction Motion Clips

Authored in Phase B5. Three pre-built motion clips for discourse and interaction
reactions. All clips were authored against parameter IDs and ranges confirmed from
`majo.cdi3.json` (parameter IDs) and `majo.vtube.json` (min/max output ranges).

Format reference: `cubism/Samples/Resources/Haru/motions/haru_g_idle.motion3.json`
— used for JSON structure and Segments array encoding only, not for parameter values.

Gate 1 result: `head_cues_reliable = true` — tap clip therefore includes a
`ParamAngleX` micro-jolt on impact (chin-up impulse at t=0.1 s).

---

## Parameter Budget (confirmed from majo.cdi3.json + majo.vtube.json)

### Axis meanings — confirmed by visual calibration renders

| Parameter ID    | Min   | Max   | Axis (confirmed)                                        |
|----------------|-------|-------|---------------------------------------------------------|
| `ParamAngleX`  | –30   | +30   | **Left/right yaw** — positive = turn right, negative = turn left |
| `ParamAngleY`  | –30   | +30   | **Up/down pitch** — positive = look up, negative = look down / nod dip |
| `ParamAngleZ`  | –30   | +30   | **Tilt/roll** — positive = lean right, negative = lean left |
| `ParamEyeBallX`| –1.0  | +1.0  | **Gaze horizontal** — positive = look right             |
| `ParamEyeBallY`| –1.0  | +1.0  | **Gaze vertical** — positive = look up                  |

**Calibration source:** AngleY confirmed as pitch (nod axis) by visual inspection of
`calibration_nod_v2.mp4` — AngleY=–10 produced a visible downward head dip at t=3.43s.
AngleX confirmed left/right by user observation of breath drift. AngleZ inferred as
tilt/roll from tap motion behaviour; not yet independently verified by a dedicated render.

**CubismBreath amplitudes on this model (from renderer config):**
AngleX ±15° (yaw), AngleY ±8° (pitch), AngleZ ±10° (roll), BodyAngleX ±4°.

**Note on look_away:** `look_away.motion3.json` uses `ParamAngleY +7` for head follow.
With AngleY = pitch, this causes the head to lift slightly (up) as the eyes go right —
producing an "up-right" thinking gaze. This is plausible; head follow would ideally use
AngleX for a lateral turn. Consider revising in round 3 look_away calibration.

---

## nod.motion3.json

**Semantic:** Discourse acknowledgement — head rises slightly (anticipation), dips
down, then returns to neutral.
**Duration:** 0.7 s | **Loop:** false | **FadeIn:** 0.1 s | **FadeOut:** 0.6 s
**Current version:** v4 (up-then-down shape with multi-keyframe easing)
**Backup:** `nod_v3.motion3.json` — previous version (AngleY only, no anticipation rise)

### Parameters used

| Parameter      | Keyframes                                                              | Values used |
|---------------|------------------------------------------------------------------------|-------------|
| `ParamAngleY` | t=0→0, t=0.12→+4, t=0.22→+5, t=0.40→–10, t=0.55→–3, t=0.70→0       | –10 to +5   |
| `ParamAngleX` | t=0→0, t=0.70→0 (hold flat)                                           | 0           |
| `ParamAngleZ` | t=0→0, t=0.70→0 (hold flat)                                           | 0           |

### Rationale

- **Up-then-down shape**: Human nods typically include a slight anticipatory raise
  before the dip. The rise to +5 (t=0.12–0.22) precedes the dip to –10 (t=0.40).
  This reads as a natural, expressive acknowledgement rather than a mechanical
  one-direction drop.
- **Multi-keyframe easing**: Multiple intermediate keyframes approximate ease-in
  (slow start of rise) and ease-out (eased return from dip) without relying on
  Bezier curves, which have uncertain behaviour with `AreBeziersRestricted: true`.
- **AngleX and AngleZ held at 0**: During the nod, CubismBreath continues driving
  all angle params. The save/restore guard in the renderer suppresses breath on
  AngleX/Y/Z while priority ≥ 2. Holding the hold curves at 0 ensures the nod reads
  clean without yaw/roll contamination.
- **FadeOutTime 0.6 s**: Increased from 0.3 s. Note: a visible snap to idle can occur
  when the motion finishes because the breath save/restore guard deactivates the
  instant priority drops from 2 → 1. The longer FadeOut gives the blend more time,
  but does not fully eliminate the snap. This is a renderer-level issue — the guard
  should ideally fade rather than switch off instantaneously. Documented for Phase D1.

### Revision history

| Version | File              | Change                                                    |
|---------|-------------------|-----------------------------------------------------------|
| v0      | nod_v0            | Initial: AngleX=–10 Linear, 0.5 s                         |
| v1      | nod_v1            | Reduced AngleX to –7; added AngleY/Z hold curves          |
| v2      | nod_v2            | Remapped primary axis: AngleY=–10 (pitch), AngleX/Z hold  |
| v3      | nod_v3            | Same as v2 confirmed by calibration render                 |
| v4      | nod (active)      | Up-then-down (+5/–10); multi-keyframe easing; 0.7 s duration |

---

## look_away.motion3.json

**Semantic:** Thinking/recalling — eyes look up-right smoothly, head follows with
a ~150 ms delay. Holds the deflected position, then smoothly returns.
**Duration:** 1.5 s | **Loop:** false | **FadeIn:** 0.15 s | **FadeOut:** 0.4 s

### Parameters used

| Parameter      | Keyframes                                                     | Peak value |
|---------------|---------------------------------------------------------------|------------|
| `ParamEyeBallX`| t=0.0→0, t=0.4→0.6, t=0.9→0.6 (hold), t=1.3→0, t=1.5→0    | +0.6       |
| `ParamEyeBallY`| t=0.0→0, t=0.4→0.15, t=0.9→0.15 (hold), t=1.3→0, t=1.5→0  | +0.15      |
| `ParamAngleY`  | t=0.0→0, t=0.55→7, t=1.05→7 (hold), t=1.45→0, t=1.5→0      | +7         |

### Rationale

- **ParamEyeBallX +0.6**: Eyes move to 60% of full rightward deflection. This is
  a convincing gaze shift without hitting the extreme that would look unnatural.
- **ParamEyeBallY +0.15**: Slight upward drift accompanies rightward gaze —
  the classic "up-right" thinking look. Kept subtle (15% of range) so as not to
  dominate the motion.
- **ParamAngleY +7**: Head follows eyes at ~35% of eye amplitude. Derivation:
  eye deflection is 0.6 out of ±1.0 = 60% of full range. 35% of that in head
  angle space: 0.35 × 0.6 × 30 ≈ 6.3, rounded to 7. The head lags by 150 ms
  (eye peak at t=0.4, head peak at t=0.55) to simulate the natural latency of
  head-following-gaze.
- A 500 ms hold period (t=0.4–0.9 for eyes, t=0.55–1.05 for head) sustains the
  "thinking" read before the return.

---

## tap.motion3.json

**Semantic:** Startled/tap reaction — head jolts sideways with damped oscillation
simulating a physics impact and recovery.
**Duration:** 1.0 s | **Loop:** false | **FadeIn:** 0.05 s | **FadeOut:** 0.3 s

**Note:** Gate 1 confirmed `head_cues_reliable = true`, so `ParamAngleX` micro-jolt
is included to simulate a slight chin-up impulse on impact.

### Parameters used

| Parameter     | Keyframes                                                                       | Values used        |
|--------------|---------------------------------------------------------------------------------|--------------------|
| `ParamAngleZ` | t=0→0, t=0.1→+8, t=0.25→–6, t=0.4→+4, t=0.55→–2, t=0.7→+1, t=1.0→0         | –6 to +8           |
| `ParamAngleX` | t=0→0, t=0.1→–3, t=0.4→0, t=1.0→0                                             | –3 to 0            |

### Rationale

- **ParamAngleZ oscillation**: Two-cycle damped oscillation simulates impact
  physics. Peak +8 (27% of ±30 range) is a sharp but believable jolt. Each
  cycle reduces amplitude by ~25%: 8→6→4→2→1→0. The oscillation period
  shortens slightly over time (0.15 s → 0.15 s → 0.15 s → 0.15 s), consistent
  with typical spring-damper decay.
- **ParamAngleX –3 micro-jolt** (chin-up): On lateral impact the head naturally
  tips back slightly. –3 (10% of ±30 range) is a subtle impulse — it adds
  physical plausibility without competing with the roll motion. Included because
  Gate 1 confirmed head tracking is reliable enough to drive AngleX cues.
- Very short FadeIn (0.05 s) ensures the jolt reads as instantaneous.
