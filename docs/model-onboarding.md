# Model Onboarding Checklist

A step-by-step workflow for evaluating and registering a new Live2D model into `assets/models/registry.json`.

## Standard workflow

```
Prerequisites (human)
    ↓
Stage 1 — Structural Audit (agent)
    │
    ├─ passes all checks ──────────────────────────────────┐
    │                                                       ↓
    └─ Stage 1.1 fails (no Expressions) ──→  VTuber Studio Export Detour
           │                                  (Expression Authoring)
           │                                       ↓ (or STOP if ineligible)
           └───────────────────────────────────────┘
                                                   ↓
                                         Stage 2 — Test Renders (agent)
                                                   ↓
                                         Stage 3 — Human Review
                                                   ↓
                                         Stage 4 — Registry Entry (agent)
```

The VTuber Studio Export Detour is only needed when the model lacks an Expressions section. Models from the Live2D Cubism Editor that include authored expressions go straight from Stage 1 → Stage 2.

---

## Prerequisites (human)

Before the agent begins, confirm:

- **Registry ID**: the `id` used in the registry must be lowercase ASCII (e.g. `"sparkle"`, `"majo"`). If the model directory or filenames use non-ASCII characters (e.g. `魔女/`), the human must supply an ASCII name before proceeding.

- **File organization**: if the model directory or any filenames contain non-ASCII characters, rename everything to ASCII before the agent starts. Create a new directory using the ASCII ID, copy all files renaming `<nonascii>.*` → `<id>.*` (e.g. `魔女.moc3` → `majo.moc3`, `魔女.8192/` → `majo.8192/`). Update the model's `.model3.json` internal `FileReferences` to match the renamed files. Delete the original non-ASCII directory. The renderer uses `fs::u8path()` for Unicode support, but keeping all paths ASCII avoids edge cases across tools.

---

## Stage 1 — Structural Audit (agent)

Read the model's `.model3.json` and assess whether it is technically complete.

### 1.1 — model3.json has Expressions section?

The `FileReferences.Expressions` array must exist and reference at least one `.exp3.json` file.

**If missing → model cannot be registered as-is.** Check whether the [VTuber Studio Export Detour](#vtuber-studio-export-detour) is viable before stopping.

### 1.2 — Expressions are emotional (not cosmetic)?

Open each `.exp3.json`. Each file must set parameters that produce a distinct, recognizable facial state (eye shape, brow, mouth curve). Feature toggles (clothing, accessories, highlights, pose variants) do not qualify.

A model needs a minimum viable emotional vocabulary:

| Minimum required | Semantic label |
|---|---|
| Neutral/resting face | `neutral` |
| At least one positive state | e.g. `happy` |
| At least one negative state | e.g. `sad` or `angry` |

**If expressions are cosmetic-only → STOP. Model is not usable.**

### 1.3 — LipSync group is populated?

`Groups[name=LipSync].Ids` must contain at least one parameter ID (typically `ParamMouthOpenY`). If empty, lip sync will silently do nothing.

**If empty → STOP. Model is not usable without lip sync.** (Exception: mute/silent avatar use case — document explicitly.)

### 1.4 — EyeBlink group is populated?

`Groups[name=EyeBlink].Ids` should contain `ParamEyeLOpen` and `ParamEyeROpen` (or equivalent). Not a hard blocker, but note if absent.

### 1.5 — Motions section has an Idle group?

`FileReferences.Motions` must include a group named `Idle` with at least one entry. This is the default loop played when no reaction cue is active.

**If missing → model renders as a frozen still. Treat as not usable unless a workaround is documented.**

---

## VTuber Studio Export Detour

**When to use:** Stage 1.1 fails (no Expressions section) and the model has a `.vtube.json` file, indicating it was built for VTuber Studio's real-time face tracking workflow rather than SDK playback.

**Why this is needed:** VTuber Studio drives facial parameters from live face capture at runtime. Its exp3 files are cosmetic hotkey overlays (blush, particle effects, clothing toggles) — not standalone emotional states. The model has no authored expressions because it was never designed to display them autonomously. This detour authors the missing expressions from scratch using the model's available facial parameters.

**If Stage 1.1 fails and there is no `.vtube.json`:** the model is a standard Cubism Editor export that simply has no expressions. Evaluate whether expressions can still be authored (proceed with the Eligibility check below), or stop and log the rejection.

### Eligibility check (agent)

Read the model's `.cdi3.json` to enumerate all parameter IDs. The model is a candidate for authoring if it has **all** of the following:

| Parameter | Purpose |
|---|---|
| `ParamMouthOpenY` | Lip sync (usually confirmed by LipSync group) |
| `ParamMouthForm` | Smile / frown curve |
| `ParamEyeLOpen`, `ParamEyeROpen` | Eye openness (usually confirmed by EyeBlink group) |
| `ParamBrowLY` | Brow height — minimum brow control |

If any of these are missing, stop. The model lacks the structural minimum for emotional expression.

### Parameter mapping (agent)

Cross-reference the model's available params against the reference expression set (Haru F01–F08). For each target emotion, keep only the params that exist in the model; drop the rest. Document which params were dropped and note the fidelity impact.

Key substitutions for models missing right-side brow controls (`ParamBrowRY`, `ParamBrowRForm`, etc.): use the left-side param only. In many rigs the "L" param drives both brows; the impact should be assessed in Stage 2 renders.

### Authoring the expression files (agent)

For each target emotion, create an `.exp3.json` file in `<model_dir>/expressions/` using only the available params. Use the same `Blend` modes as the reference (typically `Add` for brows/mouth, `Multiply` for eye openness).

Update the model's `.model3.json`:
1. Add `FileReferences.Expressions` array pointing to the new files
2. Add `FileReferences.Motions.Idle` pointing to any existing idle motion file

### Tuning loop (agent + human)

Render a labeled review video — one clip per emotion, 3 seconds each, with the emotion name overlaid — and present it for human review. For each clip the human evaluates:

- Does the expression read as the intended emotion?
- Is it visually distinct from other expressions in the set?

For any expression that reads ambiguously (looks too similar to another), adjust the conflicting parameter:

| Problem | Likely cause | Fix |
|---|---|---|
| Sad looks like angry | Both use negative `BrowLForm` | Flip `BrowLForm` positive for sad (arched/worried shape) and soften `BrowLY` |
| Two expressions look identical | Same params, similar magnitudes | Widen the delta or drop one |
| Expression is too subtle | Low-magnitude params | Increase values toward the reference model's range |

Re-render only the affected clips and rebuild the review video. Repeat until the human approves or drops the emotion.

### Dropping an emotion

If an expression cannot be made visually distinct with the available params, drop it from the emotion set. Do not include it in the registry. Document the dropped emotions and reason in the registry note or rejection log.

**Minimum to proceed:** `neutral` + at least two distinct non-neutral emotions.

---

## Stage 2 — Test Renders (agent)

Only reached if Stage 1 passes all hard checks (or the VTuber Studio Export Detour completes successfully).

### 2.1 — Render one clip per expression

For each expression in the model, create a minimal scene manifest:
- 5 seconds, no audio, transparent background
- Single cue: `{ "time": 0.0, "emotion": "<expression_id>" }`
- Output: `tests/output/<model_id>_expr_<id>.mp4`

### 2.2 — Render one clip per motion group

For each named motion group, create a minimal scene manifest:
- 5 seconds, no audio
- Single cue: `{ "time": 0.0, "reaction": "<group_name>" }`
- Output: `tests/output/<model_id>_motion_<group>.mp4`

### 2.3 — Render a lip sync test

One short render with a real WAV file to confirm mouth movement is visible.

---

## Stage 3 — Human Review

Watch every clip produced in Stage 2 and fill in the mapping table:

### Emotion mapping

| Expression ID | What it looks like | Semantic label to assign | Notes |
|---|---|---|---|
| F01 | | | |
| F02 | | | |
| ... | | | |

Assign each expression exactly one semantic label from the approved vocabulary:
`neutral`, `curious`, `angry`, `sad`, `happy`, `surprised`, `embarrassed`, `bored`

If an expression doesn't cleanly map to any label, leave it unmapped (do not force a label).

**Minimum required to proceed:** `neutral` + at least two others.

### Reaction mapping

| Motion group | What it looks like | Semantic label to assign | Notes |
|---|---|---|---|
| Idle | | | |
| TapBody | | | |
| ... | | | |

Assign each motion group a semantic label. Required: `idle`. Optional: `tap`, `nod`, `wave`, etc.

---

## Stage 4 — Registry Entry (agent)

Write the registry entry based on Stage 3 output:

```json
{
  "id": "<model_id>",
  "path": "<relative/path/to/Model.model3.json>",
  "emotions": {
    "neutral":   { "id": "<expr_id>", "note": "<human-verified description>" },
    "happy":     { "id": "<expr_id>", "note": "<human-verified description>" }
  },
  "reactions": {
    "idle":      { "id": "<motion_group>", "note": "<human-verified description>" }
  }
}
```

Run the full test suite (`tests/fixtures/`) with the new model subbed in for at least one fixture to confirm it renders without errors.

---

## Rejection Log

Models evaluated and rejected, with reason:

| Model | Rejection stage | Reason |
|---|---|---|
| Sparkle | 1.1 | No Expressions section in model3.json; expression files are cosmetic toggles (legs, highlights, hand pose), not facial emotions. LipSync and EyeBlink groups are empty. VTube Studio origin — designed for real-time face tracking, not SDK playback. |
| 魔女 → registered as `majo` | 1.1 (recovered via VTuber Studio Export Detour) | No Expressions or Motions section in model3.json. 12 exp3 files were all cosmetic VTube Studio hotkey toggles. LipSync and EyeBlink groups correctly populated. Recovered via Expression Authoring path: 8 emotions authored, 6 approved after human review (`neutral`, `happy`, `surprised`, `bored`, `sad`, `angry`); `curious` and `embarrassed` dropped as indistinct on this rig. Expressions in `majo/expressions/`, Motions.Idle wired to `Scene1.motion3.json`. Files moved from `魔女/` to `majo/` with ASCII renames. |
