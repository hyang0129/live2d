# Motion Definition

## Motions vs Expressions

**Motions** are clips that move the model — head angles, gaze, body position.
Their visual result depends on the physical state of the model at the moment
they begin.

**Expressions** are clips that convey an emotional state — typically blendshape
weights, eye openness, brow shape, mouth curve. All expressions must be
**entry-independent** (see below): they must produce a consistent result from
any starting point. A clip that cannot be made entry-independent **cannot** be
classified as an expression — no exceptions.

The classification rule:

> If the intended semantic of the clip is *movement* → it is a **motion**.
> If the intended semantic is *emotional state* → it is an **expression**.

There is natural overlap (an expression clip may incidentally move the brow
angle; a motion clip may incidentally affect an expression parameter), but the
entry-independence constraint on expressions is hard: it is the property that
distinguishes the two categories, not just a guideline.

---

## Motion Entry Classification

Every motion clip is classified on the following axis:

### Entry-Independent

The clip produces a consistent, human-reviewable result regardless of the
model's parameter state at entry. The motion either:

- works entirely in absolute keyframe space (sets parameters to fixed values),
  or
- operates on parameters whose starting variance is perceptually irrelevant
  (e.g. blink — the starting lid position matters less than the closure
  event).

**Examples:** blink, most expression clips, any motion that begins with an
explicit snap-to-neutral on all parameters it drives.

**Constraint:** none. Can be triggered at any time.

---

### Entry-Dependent

The clip produces a result that is visually correct only if the model's
parameter state at entry falls within a defined **valid entry range**. Outside
that range the motion will read as broken, unnatural, or physically implausible
to a human reviewer.

Entry-dependence typically arises when:

- the clip is authored as a *delta* from an assumed neutral pose (e.g. a nod
  authored as `AngleY −10` relative to `0` will overshoot badly if entry
  `AngleY` is already `−15`), or
- the clip includes a preceding normalization gesture (e.g. snap-to-look-
  forward) that is only plausible from a limited initial deflection.

**Examples:** delta-AngleY nod (invalid if head already pitched far down),
snap-to-forward + nod sequence (invalid if head is far left or right).

Every entry-dependent clip **must** declare a `valid_entry` block in its
motion registry entry (see below).

---

## Valid Entry Range Declaration

Entry-dependent motions define their valid entry range as a set of parameter
bounds. Any parameter not listed is considered unconstrained.

```json
"valid_entry": {
  "ParamAngleY": { "min": -8, "max": 8 },
  "ParamAngleX": { "min": -20, "max": 20 }
}
```

The bounds represent the parameter values, in the model's native units, that
must hold at the moment the motion begins. If any constrained parameter is
outside its declared range, the motion is considered **out-of-range**.

---

## Out-of-Range Handling

When a motion is triggered and the entry check fails, the system resolves the
violation according to the configured mode.

Three modes are available. **Default: implicit.**

### None Mode (skip check)

Entry check is not performed. The motion plays immediately regardless of the
model's current parameter state. Used when the author wants to declare
`valid_entry` for documentation purposes without enforcing it at runtime, or
to baseline a review render that shows the uncorrected behaviour.

### Implicit Mode (normalise-then-play)

The renderer automatically inserts a **normalisation motion** that moves the
constrained parameters into valid range before starting the requested clip.

#### Movement shape

Parameters are moved using a **smoothstep ease-in/ease-out** curve:

```
f(t) = t²(3 − 2t)   for t ∈ [0, 1]
```

Velocity is zero at both endpoints. The head accelerates into the move and
decelerates into the target boundary. There is no snap-start or snap-stop.
This is intentional: a constant-velocity lurch reads as mechanical; the
smoothstep reads as a deliberate, volitional adjustment.

#### Rate and duration

- The **normalise rate** controls peak speed (units/second). By default it is
  **auto-computed** as `2 × max_breath_speed` for the constrained parameter,
  where `max_breath_speed = amplitude × weight × 2π / period`. For
  `ParamAngleX` on the majo model: `15 × 0.5 × 2π / 6.5345 ≈ 7.2 units/s`;
  default normalise rate ≈ **14.4 units/s**. The auto rate means
  normalisation moves at roughly twice the speed of the natural idle
  oscillation — perceptibly intentional, but not jarring.
- A **minimum normalisation duration of 0.1 s** is enforced. Even when the
  violation is very small (< 1 unit), the movement takes at least 0.1 s,
  ensuring the ease-in/ease-out curve is perceptible rather than resolving
  in a single frame.
- The duration is determined by the worst-case (largest) violation across all
  constrained parameters.
- The combined duration (normalisation + clip) will exceed the originally
  requested trigger time.

#### Warning log

A warning is emitted at the point of trigger containing:
- which parameters were out of range and by how much,
- the normalisation rate used and resulting duration,
- the estimated actual start time of the requested clip,
- the recommended pre-trigger lead time.

```
WARN [motion] nod: entry out of range — ParamAngleX=7.0(valid:-5.0..5.0)
     | normalise_rate=14.4 units/s normalisation_duration=0.139s
     | actual_clip_start=t=2.139 (requested t=2.000)
     | to hit t=2.000 trigger normalisation at t=1.861
```

The normalisation motion runs at the same breath guard priority as the
requested clip, so the breath guard activates at the start of normalisation
and deactivates after the clip completes. The full sequence from the user's
perspective is:

```
idle (breath running) → ease-in/out normalise to boundary → clip plays → breath guard fades out → idle resumes
```

### Explicit Mode (error-and-halt)

The renderer emits a structured **error** and does not play the motion.

```json
{
  "error": "motion_entry_out_of_range",
  "motion": "nod",
  "trigger_time": 4.0,
  "violations": [
    { "param": "ParamAngleY", "value": -14, "valid_min": -8, "valid_max": 8 }
  ],
  "normalise_rate": 15.0,
  "estimated_normalisation_duration": 0.40,
  "recommended_trigger_time": 3.60
}
```

No normalisation is performed. The error is logged and returned to the caller.

Explicit mode is intended for **scripted pipeline** use (e.g. a scene manifest
rendered by video_agent). The scripting agent reads the error, adjusts the
trigger time using `recommended_trigger_time`, and re-submits. The estimated
normalisation duration is included so the agent can also choose to insert an
explicit normalisation cue rather than simply shifting the trigger.

The mode is set per-trigger-call and can also be set as a renderer-level
default.

---

## Motion Registry Entry Format

```json
{
  "id": "nod",
  "file": "assets/models/majo/motions/nod.motion3.json",
  "entry": "dependent",
  "valid_entry": {
    "ParamAngleX": { "min": -5, "max": 5 }
  },
  "out_of_range_mode": "implicit"
}
```

`normalise_rate` may be omitted (default `0` = auto-compute from breath speed).
Include it only to override the auto rate, e.g. for a motion that requires
unusually slow or fast centering.

| Field | Values | Notes |
|---|---|---|
| `entry` | `independent`, `dependent` | Independent clips omit `valid_entry` |
| `valid_entry` | parameter bounds map | Required if `entry = dependent` |
| `normalise_rate` | float units/s, or `0` | `0` = auto (2× breath max speed for the constrained param). Omit to use auto. |
| `out_of_range_mode` | `none`, `implicit`, `explicit` | Default: `implicit` |

---

## Relationship to Breath Guard

The breath guard mode (no-guard vs lerp-guard, documented in
`breath-guard-findings.md`) interacts with implicit-mode normalisation:

- The breath guard activates at the start of the normalisation motion (not at
  the start of the clip), so the guard duration covers the full
  normalise-then-play sequence.
- The lerp-guard fade-out begins after the clip ends, exactly as it would
  without normalisation.
- Explicit mode errors fire before any motion or guard state is modified, so
  they have no breath guard side-effects.
