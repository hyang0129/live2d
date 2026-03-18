# Agent Team Spec — Live2D Behaviour Authoring

**Date:** 2026-03-17
**Scope:** Changes within `live2d/` only. Cross-repo work (Phase E, video_agent integration) is excluded.
**Implements:** Roadmap Phases A2–D2 (remaining work after research and spec v1 are complete)

---

## Phases Covered

```
A2   Write behaviour-authoring-workflow.md
A3   Verify renderer binary builds
B1   Majo pre-authoring audit (audit.md)
B2   Fix expression fade times
B3   Head cue conflict test (BLOCKING)
B4   Add gaze drift keyframes to idle motion
B5   Author nod, look_away, tap reaction clips
C1   Review render — round 1
C2–C4  Review loop (N rounds)
C5   Registry update + spec compliance
D1–D2  Workflow doc finalisation and approval
```

---

## Agent Roster

| Agent | Role | Owned phases |
|---|---|---|
| [OrchestratorAgent](#orchestratoragent) | Phase sequencing, human gates, state machine | All phases (router only) |
| [AuditAgent](#auditagent) | Read-only analysis of majo assets | A3, B1 |
| [AssetAuthorAgent](#assetauthoragent) | Author / patch `.exp3.json` and `.motion3.json` | B2, B4, B5, revision half of C2–C4 |
| [RenderTestAgent](#rendertestagent) | Execute renders, produce labeled videos | B3 (cue conflict), C1, re-renders in C3 |
| [ReviewLoopAgent](#reviewloopagent) | Interpret human feedback, write `round_N.json`, dispatch revisions | C2–C4 (interpretation half) |
| [RegistryAgent](#registryagent) | Update `registry.json`, run spec compliance | C5 |
| [DocAgent](#docagent) | Write and finalise `behaviour-authoring-workflow.md` | A2, D1–D2 |

---

## Agent Definitions

### OrchestratorAgent

**Type:** Stateful supervisor
**Model:** claude-opus-4-6 (needs strong reasoning for gate decisions)

**Responsibilities:**
- Owns the phase sequence from A2 to D2.
- Spawns sub-agents with complete task briefs; does not read files itself.
- Holds two hard human gates that must not be bypassed:
  - **Gate 1 — after B3:** receive human verdict on head cue conflict test result. The outcome (cues reliable / unreliable) controls how AssetAuthorAgent encodes head movement in B5.
  - **Gate 2 — after each review render (C1, C3):** receive human feedback before any revision begins.
- Enforces the **stopping rule**: if the same clip is on its 4th revision with no approval, escalates to the human with an explicit "continue / drop / reject model" prompt.
- After D2 approval, posts a final summary listing every approved behaviour, every dropped behaviour (with reason), and open risks carried forward.

**State it maintains between turns:**
```json
{
  "current_phase": "B3",
  "head_cues_reliable": null,
  "review_round": 0,
  "pending_clips": [],
  "revision_counts": {}
}
```

**Does NOT:**
Read or write files. Delegate all file I/O to sub-agents.

---

### AuditAgent

**Type:** Read-only analyst
**Model:** claude-sonnet-4-6

**Responsibilities:**

**Phase A3 — build verification:**
- Run the renderer CMake build and capture output.
- Report: build succeeded / failed. If failed, include the first compiler error verbatim and stop — do not attempt fixes.

**Phase B1 — majo pre-authoring audit:**

Reads (in order):
1. `assets/models/majo/majo.cdi3.json` — extracts full parameter ID list and ranges.
2. All `assets/models/majo/expressions/*.exp3.json` (6 files) — checks `FadeInTime`, `FadeOutTime`, and parameter region coverage (brows, eyes, mouth).
3. `assets/models/majo/motions/` — lists existing `.motion3.json` files, opens the idle file, checks for `ParamAngleX`, `ParamAngleZ` keyframe amplitude and presence of `ParamEyeBallX`/`ParamEyeBallY`.
4. `assets/models/majo/majo.model3.json` — confirms `FileReferences.Motions` and `Expressions` entries.

Produces `assets/models/majo/audit.md` with three sections:

```markdown
## Expression audit
| File | FadeInTime | FadeOutTime | Brows params | Eyes params | Mouth params | Status |

## Idle motion audit
| Parameter | Present | Min keyframe | Max keyframe | Status |

## Reaction clips
| Label | File exists | Registered in model3.json |
```

**Termination:** Returns `audit.md` path to OrchestratorAgent. Does not modify any files.

---

### AssetAuthorAgent

**Type:** File writer
**Model:** claude-sonnet-4-6

**Responsibilities:**

**Phase B2 — expression fade time fixes:**
- Opens each `.exp3.json` flagged by the audit as having `FadeInTime` < 0.15 or `FadeOutTime` < 0.3.
- Sets `FadeInTime` = 0.2 and `FadeOutTime` = 0.4 on non-compliant files.
- Does not change any parameter values — this is a metadata correctness fix only.
- Reports exactly which files were patched.

**Phase B4 — idle gaze drift:**
- Opens the idle motion file.
- If `ParamEyeBallX` and `ParamEyeBallY` are absent, adds two curve segments:
  - Slow sinusoidal drift: amplitude ±0.2 on each axis, period spread across idle duration.
  - Uses `InversedStepped` segment type (smooth easing, not linear).
- If parameters are present, verifies amplitude ≥ 0.1; if below threshold, increases to 0.15.
- Saves a versioned backup as `<filename>_v0.motion3.json` before editing.

**Phase B5 — reaction clip authoring:**

For each of `nod`, `look_away`, `tap`:

1. Read `majo.cdi3.json` — identify exact parameter IDs and min/max ranges. Never use parameter names from other models.
2. Read `cubism/Samples/Resources/Haru/motions/` (Haru's TapBody and Idle files) — for JSON schema and curve encoding format only.
3. Author the clip following the spec table:

| Clip | Technique | Head encoding if cues reliable | Head encoding if cues unreliable |
|---|---|---|---|
| `nod` | `ParamAngleX` dip –10° and return over 0.5 s | Keyframe curve only (motion priority system) | Same — motion clips always use keyframes regardless |
| `look_away` | `ParamEyeBallX/Y` smooth arc; `ParamAngleY` offset 150 ms behind, ~35% amplitude | Include `ParamAngleY` keyframes in clip | Same — head movement via keyframes either way |
| `tap` | `ParamAngleZ` ±8° jolt, two sub-cycles, recovery, total 1.0 s | Include `ParamAngleX` micro-jolt | Omit `ParamAngleX` (snap risk) |

> Note: the Gate 1 result (head cues reliable/unreliable) affects only whether the
> `tap` clip includes an `AngleX` micro-jolt. All other head movement is authored as
> keyframe curves regardless, since motion clips always use the interpolation system.

4. Wire each clip into `majo.model3.json` under `FileReferences.Motions.<group>[<i>]`.
5. Write authoring rationale (parameter choices, initial value estimates, format reference used) to `assets/models/majo/motions/README.md`.
6. Save versioned backup of any overwritten file as `<filename>_v0.motion3.json`.

**Revision cycles (C2–C4):**
- Receives a list of `{ label, proposed_fix }` entries from ReviewLoopAgent.
- For each: applies the fix, saves the previous version as `_v<N-1>.json`, writes a brief change note to `motions/README.md`.
- Returns a list of patched files to OrchestratorAgent so RenderTestAgent can re-render only those clips.

**Constraints:**
- Never copies parameter names or values from another model's motion files.
- Always backs up before overwriting.
- Does not run renders.

---

### RenderTestAgent

**Type:** Script runner + video producer
**Model:** claude-sonnet-4-6

**Responsibilities:**

**Phase B3 — head cue conflict test:**

1. Write `tests/fixtures/majo_cue_test.json` — a manifest that sends explicit `head` cues (`AngleX` = +15°, `AngleY` = –10°) at t=1.0 s and t=3.0 s, and `gaze` cues (`ParamEyeBallX` = 0.6) at t=2.0 s. Also include a combined `emotion:"happy"` + `reaction:"idle"` segment to test interference.
2. Run the renderer against this manifest.
3. Inspect the output video or renderer logs:
   - **Pass criterion:** head visibly moves to the cued angle and holds for ~0.5 s before drift resumes.
   - **Fail criterion:** head remains in breath-cycle position regardless of cue values.
4. Report verdict (`head_cues_reliable: true/false`) and raw evidence (frame timestamp, observed angle, renderer log excerpt) to OrchestratorAgent.
5. Also report gaze cue snap behaviour observed.

**Phase C1 — review render (full behaviour set):**

1. Run `scripts/behavior_review.py` against majo with the full expression and reaction set.
2. If the script does not support a required test case (gaze-in-motion, physics overshoot, cue-plus-reaction combos), write a targeted one-off manifest for that case and render it directly via the renderer binary, then annotate with FFmpeg title filters.
3. Assemble all clips into a single labeled review video.
4. Output: `tests/fixtures/majo_review/round_<N>_review.mp4` and a corresponding `round_<N>_manifest.json` listing each clip's label, start time, and duration in the video.

**Phase C3 — targeted re-renders:**
- Receives a list of clip labels that were revised.
- Renders only those clips — not the full set.
- Labels each clip with `[REVISED r<N>]` overlay via FFmpeg.
- Output: `tests/fixtures/majo_review/round_<N>_revised.mp4`.

**Does NOT:**
Edit any `.exp3.json` or `.motion3.json`. Reads and runs only.

---

### ReviewLoopAgent

**Type:** Feedback interpreter
**Model:** claude-opus-4-6 (needs nuanced natural-language parsing)

**Responsibilities (Phase C2–C4, interpretation half):**

Receives:
- Human's plain-English feedback (text or voice transcript).
- `round_<N>_manifest.json` (clip labels and timestamps from RenderTestAgent).

Produces `assets/models/majo/review_log/round_<N>.json`:

```json
{
  "round": 1,
  "clips": [
    {
      "label": "nod",
      "type": "reaction",
      "verdict": "Revise",
      "human_quote": "the nod goes too deep, looks like a bow",
      "agent_diagnosis": "ParamAngleX peak magnitude too large (~−20°)",
      "proposed_fix": "Reduce ParamAngleX peak from −20° to −10°; widen return curve from 0.2 s to 0.3 s"
    }
  ]
}
```

**Interpretation rules:**
- Explicit approval ("looks good", "that's fine") → `Approved`.
- Any criticism, qualifier, or "a bit off" → `Revise`.
- No mention of a clip: treat as `Approved` **only if** human explicitly said "everything else looks good." Otherwise set `verdict: "Unreviewed"` and flag to OrchestratorAgent.
- If human's description is a visual observation, map it to a parameter: "goes too deep" → magnitude too large; "too fast" → keyframe duration too short; "snaps" → FadeInTime = 0 or missing curve easing; "overshoots" → physics interaction, reduce amplitude or add damping keyframes.
- If the mapping is genuinely ambiguous, do **not** guess. Insert `"proposed_fix": null` and a `"clarification_needed"` field with a single, precise question. OrchestratorAgent will surface this to the human.

**Does NOT:**
Write any `.json` motion or expression files. Hands `proposed_fix` entries to AssetAuthorAgent.

---

### RegistryAgent

**Type:** Registry writer + compliance checker
**Model:** claude-sonnet-4-6

**Responsibilities (Phase C5):**

1. Read `assets/models/registry.json` and `assets/models/majo/review_log/` (all round files).
2. Collect all `Approved` entries across all rounds.
3. Update the majo entry in `registry.json`:
   - `emotions`: list of approved expression labels.
   - `reactions`: list of approved reaction labels.
   - `gaps`: list of behaviours with `verdict: "Drop"`, each with `reason` from the round log.
4. Run `scripts/run_tests.sh` (or equivalent fixture suite) — report pass/fail. Do not interpret test failures; surface them verbatim to OrchestratorAgent.

**Phase C5 — spec compliance check:**

Map the approved set against Avatar Behaviour Spec v1:

| Spec requirement | Tier | Approved? |
|---|---|---|
| `neutral` expression | Mandatory | ? |
| `happy` expression | Mandatory | ? |
| `serious` expression | Mandatory | ? |
| `surprised` expression | Mandatory | ? |
| `sad` expression | Threshold | ? |
| `angry` expression | Threshold | ? |
| `idle` reaction | Mandatory | ? |
| `nod` reaction | Threshold | ? |
| `look_away` reaction | Threshold | ? |
| `tap` reaction | Threshold | ? |

If any mandatory or threshold item is absent: produce a compliance gap report with the exact language for OrchestratorAgent to relay to the human:

> "Majo cannot meet spec minimum [X] because [reason]. Options: (A) continue iteration, (B) accept as a limited model with documented gap, (C) reject model."

---

### DocAgent

**Type:** Document writer
**Model:** claude-sonnet-4-6

**Responsibilities:**

**Phase A2 — initial workflow document:**
- Reads `docs/roadmap.md` Deliverable 2 section (already contains the complete workflow structure).
- Writes `spec/v1/behaviour-authoring-workflow.md` as a clean, standalone document — no roadmap references, written as a how-to guide an agent can follow for any new model.
- Does not wait for majo work to complete; the roadmap section is sufficiently defined to write the first draft now.

**Phase D1 — post-majo update:**
- Reads all `review_log/round_*.json` files and `assets/models/majo/motions/README.md`.
- Identifies any divergences between the workflow as written in A2 and what actually happened during majo authoring (e.g., additional edge cases, a phase that ran in a different order, a technique that didn't work as described).
- Produces a diff-style section at the end of the workflow doc: `## Lessons from Majo (Reference Implementation)`.
- Updates any Phase descriptions that were materially wrong.

**Phase D2 — approval gate:**
- Prepares a clean final version of the workflow doc for human review.
- After human approval, sets the document header status to `Status: Approved — v1.0`.

---

## Orchestration Flow

```
OrchestratorAgent
│
├─► DocAgent [A2] ── write spec/v1/behaviour-authoring-workflow.md
│
├─► AuditAgent [A3] ── verify renderer build
│   └─ FAIL: halt; report build error to human. No further work until fixed.
│
├─► AuditAgent [B1] ── majo audit.md
│
├─► AssetAuthorAgent [B2] ── fix fade times (if any flagged)
│   (runs in parallel with B3 setup — does not affect B3)
│
├─► RenderTestAgent [B3] ── head cue conflict test
│   └─► ◉ GATE 1: human reviews cue test video
│       OrchestratorAgent records head_cues_reliable = true/false
│       Briefs AssetAuthorAgent with Gate 1 result before dispatching B4/B5
│
├─► AssetAuthorAgent [B4] ── idle gaze drift
├─► AssetAuthorAgent [B5] ── author nod, look_away, tap
│   (B4 and B5 run sequentially — B5 may depend on idle motion state)
│
├─► RenderTestAgent [C1] ── full review render → round_1_review.mp4
│   └─► ◉ GATE 2: human watches review video, gives plain-English feedback
│
├─ [LOOP until all clips resolved or dropped] ──────────────────────────────┐
│   ReviewLoopAgent [C2] ── interpret feedback → round_N.json              │
│   AssetAuthorAgent [C2] ── apply proposed_fixes, save versioned backups  │
│   RenderTestAgent  [C3] ── re-render only revised clips                  │
│   └─► ◉ GATE 2 (repeat): human reviews changed clips only               │
│   OrchestratorAgent checks: any clip at revision ≥ 3? → escalate        │
└───────────────────────────────────────────────────────────────────────────┘
│
├─► RegistryAgent [C5] ── registry update + compliance check
│   └─ compliance gap? → OrchestratorAgent escalates to human
│
├─► DocAgent [D1] ── update workflow doc with majo lessons
│   └─► ◉ GATE 3: human reviews final workflow doc
│       DocAgent [D2] ── mark doc Approved — v1.0
│
└─► OrchestratorAgent: final summary (approved behaviours, gaps, open risks)
```

---

## Human Gates (summary)

| Gate | Trigger | What human sees | Human's job |
|---|---|---|---|
| Gate 1 | After B3 cue conflict render | `majo_cue_test` render + RenderTestAgent verdict | Confirm or override the pass/fail verdict |
| Gate 2 (R1) | After C1 full review render | `round_1_review.mp4` + clip index | Give plain-English feedback per clip |
| Gate 2 (R2+) | After each targeted re-render | `round_N_revised.mp4` (revised clips only) | Approve or give further feedback per changed clip |
| Gate 3 | After D1 doc update | `spec/v1/behaviour-authoring-workflow.md` | Approve or request edits |

Human input is **plain English only**. Agents interpret and translate into structured records. The human never writes JSON or fills out schemas.

---

## File Outputs by Phase

| Phase | Agent | Output file(s) |
|---|---|---|
| A2 | DocAgent | `spec/v1/behaviour-authoring-workflow.md` |
| B1 | AuditAgent | `assets/models/majo/audit.md` |
| B2 | AssetAuthorAgent | patched `expressions/*.exp3.json` |
| B3 | RenderTestAgent | `tests/fixtures/majo_cue_test.json`, cue test render |
| B4 | AssetAuthorAgent | updated `motions/<idle>.motion3.json`, `_v0` backup |
| B5 | AssetAuthorAgent | `motions/nod.motion3.json`, `look_away.motion3.json`, `tap.motion3.json`; updated `majo.model3.json`; `motions/README.md` |
| C1 | RenderTestAgent | `tests/fixtures/majo_review/round_1_review.mp4`, `round_1_manifest.json` |
| C2 | ReviewLoopAgent | `assets/models/majo/review_log/round_N.json` |
| C2 | AssetAuthorAgent | revised motion/expression files + `_v<N-1>` backups |
| C3 | RenderTestAgent | `tests/fixtures/majo_review/round_N_revised.mp4` |
| C5 | RegistryAgent | updated `assets/models/registry.json` |
| D1 | DocAgent | updated `spec/v1/behaviour-authoring-workflow.md` |

---

## Constraints and Guardrails

1. **No cross-repo file writes.** All outputs are within `live2d/`. Phase E (video_agent integration) is explicitly out of scope here.
2. **Parameter names from `.cdi3.json` only.** AssetAuthorAgent must read `majo.cdi3.json` before authoring any motion file. Using parameter names from Haru or any other model is a bug.
3. **Versioned backups before any overwrite.** AssetAuthorAgent saves `_v<N>` copies. RenderTestAgent never writes motion or expression files.
4. **Stopping rule.** OrchestratorAgent enforces: ≥ 3 revisions with no approval → human escalation, not a 4th automatic revision.
5. **Gate 1 result propagates forward.** OrchestratorAgent records `head_cues_reliable` and includes it in every subsequent brief to AssetAuthorAgent. The default assumption (before Gate 1) is `unreliable` — no head-cue-dependent encoding is authored until confirmed.
6. **Renderer build failure halts all work.** If AuditAgent reports a build failure in A3, OrchestratorAgent stops and reports the error. No authoring proceeds on a broken build.
