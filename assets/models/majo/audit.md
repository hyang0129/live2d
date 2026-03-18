# Majo Pre-Authoring Audit

Date: 2026-03-17

## Expression audit
| File | FadeInTime | FadeOutTime | Brows params | Eyes params | Mouth params | Status |
|---|---|---|---|---|---|---|
| angry.exp3.json | N/A (missing) | N/A (missing) | ParamBrowLY, ParamBrowLForm | — | ParamMouthForm, ParamMouthOpenY | NON-COMPLIANT |
| bored.exp3.json | N/A (missing) | N/A (missing) | ParamBrowLForm | ParamEyeLOpen, ParamEyeROpen | ParamMouthForm | NON-COMPLIANT |
| curious.exp3.json | N/A (missing) | N/A (missing) | ParamBrowLY, ParamBrowLForm | — | ParamMouthOpenY | NON-COMPLIANT |
| embarrassed.exp3.json | N/A (missing) | N/A (missing) | ParamBrowLY, ParamBrowLForm | ParamEyeLOpen, ParamEyeROpen | ParamMouthForm | NON-COMPLIANT |
| happy.exp3.json | N/A (missing) | N/A (missing) | ParamBrowLY | ParamEyeLOpen, ParamEyeLSmile, ParamEyeROpen, ParamEyeRSmile | — | NON-COMPLIANT |
| neutral.exp3.json | N/A (missing) | N/A (missing) | — | — | ParamMouthForm | NON-COMPLIANT |
| sad.exp3.json | N/A (missing) | N/A (missing) | ParamBrowLY, ParamBrowLForm | ParamEyeLOpen, ParamEyeROpen | ParamMouthForm | NON-COMPLIANT |
| surprised.exp3.json | N/A (missing) | N/A (missing) | ParamBrowLY | ParamEyeLOpen, ParamEyeROpen | ParamMouthForm | NON-COMPLIANT |

**Notes:**
- All 8 expression files are missing `FadeInTime` and `FadeOutTime` fields entirely (not just below threshold — the keys are absent). This violates both the ≥ 0.15 and ≥ 0.30 compliance thresholds.
- `angry.exp3.json`: missing Eyes region params.
- `bored.exp3.json`: OK on all three regions.
- `curious.exp3.json`: missing Eyes region params.
- `embarrassed.exp3.json`: OK on all three regions.
- `happy.exp3.json`: missing Mouth region params.
- `neutral.exp3.json`: missing Brows and Eyes region params; only one param set at all.
- `sad.exp3.json`: OK on all three regions.
- `surprised.exp3.json`: OK on all three regions.

## Idle motion audit
| Parameter | Present | Min keyframe | Max keyframe | Status |
|---|---|---|---|---|
| ParamAngleX | No | — | — | MISSING |
| ParamAngleZ | No | — | — | MISSING |
| ParamEyeBallX | No | — | — | MISSING |
| ParamEyeBallY | No | — | — | MISSING |

**Notes:**
- `Scene1.motion3.json` contains 7 curves: `Param69`, `Param25`, `Param26`, `Param27`, `Param70`, `Param28`, `Param30`. None of these are standard Cubism parameter IDs for head angle or gaze. The idle motion drives custom/effect parameters only and contains no head-angle or eye-gaze animation at all.

## Reaction clips
| Label | File exists | Registered in majo.model3.json |
|---|---|---|
| idle | Yes (Scene1.motion3.json) | Yes (under Motions.Idle) |
| nod | No | No |
| look_away | No | No |
| tap | No | No |

**Notes:**
- `majo.model3.json` registers only a single motion group (`Idle`) pointing to `Scene1.motion3.json`. No `nod`, `look_away`, or `tap` clips exist on disk or in the registry.
- There is no `motions/` subdirectory; the single motion file lives in the model root.

## Summary

- **All 8 expressions are missing `FadeInTime` and `FadeOutTime` fields** — these must be added (≥ 0.15 s and ≥ 0.30 s respectively) to every `.exp3.json` before authoring.
- **5 of 8 expressions fail region coverage**: `angry` and `curious` lack Eye params; `happy` lacks Mouth params; `neutral` lacks both Brows and Eyes params. Each of these files needs the missing region parameters authored or carried over from the default pose.
- **The idle motion (`Scene1.motion3.json`) contains no head-angle or gaze curves** — `ParamAngleX`, `ParamAngleZ`, `ParamEyeBallX`, and `ParamEyeBallY` are all absent. A proper idle motion must be authored or replaced before the renderer can produce natural idle movement.
- **Reaction clips `nod`, `look_away`, and `tap` do not exist** — neither the motion files nor their `majo.model3.json` entries are present. These must be created and registered before the cue sequencer can trigger them.
- **What is already compliant**: all 8 expression filenames match the required set; all 8 are registered in `majo.model3.json`; the model file correctly references the MOC, textures, physics, and display-info assets; the `idle` motion entry is registered (though the motion content needs replacement).
