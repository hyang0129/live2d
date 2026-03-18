# Behaviour Examples

Example scene manifests demonstrating each behaviour from Avatar Behaviour Spec v1.

These are both documentation (shows the exact cue format for each behaviour) and runnable test manifests (pass directly to `live2d-render --scene <file>`).

## Audio placeholder

All manifests reference `assets/behaviour-examples/audio/silence_8s.wav`. Generate it once:

```bash
ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 8 assets/behaviour-examples/audio/silence_8s.wav
```

## Files

| File | Demonstrates | Duration |
|---|---|---|
| `expression_neutral.json` | neutral expression | 5 s |
| `expression_happy.json` | happy expression | 5 s |
| `expression_serious.json` | serious expression | 5 s |
| `expression_surprised.json` | surprised expression | 5 s |
| `expression_sad.json` | sad expression | 5 s |
| `expression_angry.json` | angry expression | 5 s |
| `expression_bored.json` | bored expression (enhancement) | 5 s |
| `expression_curious.json` | curious expression (enhancement) | 5 s |
| `expression_embarrassed.json` | embarrassed expression (enhancement) | 5 s |
| `reaction_nod.json` | nod reaction | 5 s |
| `reaction_look_away.json` | look_away reaction | 5 s |
| `reaction_tap.json` | tap reaction | 5 s |
| `reaction_shake.json` | shake reaction (enhancement) | 5 s |
| `combined_review.json` | all expressions + reactions in sequence | ~75 s |

## Pattern

Expression examples: neutral at t=0, switch to target at t=2, return to neutral at t=4.
Reaction examples: neutral at t=0, reaction triggered at t=2, holds to end.
Combined: each behaviour gets ~5 s of isolation in sequence.
