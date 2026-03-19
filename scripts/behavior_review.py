#!/usr/bin/env python3
"""
Behavior Review Generator

Two modes:

  Onboarding mode  (Stage 2 — pre-registration):
    python scripts/behavior_review.py --model-path majo/majo.model3.json
    Reads expressions and motions directly from the model file. No registry
    entry required. Use this during onboarding Stage 2 to verify expressions
    look correct before writing the registry entry, and during the VTuber
    Studio Export Detour for the expression tuning loop.

  Registry mode  (post-registration):
    python scripts/behavior_review.py --model majo
    Reads emotions and reactions from the registry entry. Use this for
    ongoing verification or after editing a registered model.

In both modes a labeled review video is produced: one segment per behavior
(emotion/reaction), with a text overlay naming it, burned into the lower
third. Lip sync audio loops throughout by default.

Usage
-----
    python scripts/behavior_review.py --model-path majo/majo.model3.json
    python scripts/behavior_review.py --model majo
    python scripts/behavior_review.py --model haru --duration 3
    python scripts/behavior_review.py --model-path ... --no-lipsync
    python scripts/behavior_review.py --model majo --output custom.mp4
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT              = Path(__file__).resolve().parent.parent
TEMPLATE_AUDIO    = ROOT / "tests/fixtures/cheesetest/wav/scene_01.wav"
TEMPLATE_MANIFEST = ROOT / "tests/fixtures/cheesetest/scene_01_manifest.json"
REGISTRY_PATH     = ROOT / "assets/models/registry.json"
DRAFT_ID          = "__review_draft__"

# Per-behavior review criteria displayed as a top overlay in the review video.
# Key: the emotion alias or reaction alias used in the registry / cue.
# Value: one line (~75 chars max) stating what PASS looks like.
# Add entries here whenever a new behavior is registered.
REVIEW_CRITERIA: dict[str, str] = {
    # ── base expressions ────────────────────────────────────────────────────
    "neutral":      "PASS: calm resting face — slight mouth curve, eyes open",
    "happy":        "PASS: warm smile, eyes closed/squinting, brows raised",
    "surprised":    "PASS: wide eyes x2, raised brow, open mouth",
    "bored":        "PASS: heavy-lidded 80%, flat mouth — disengaged",
    "sad":          "PASS: soft eyes, arched brow, strongly downturned mouth",
    "angry":        "PASS: brow fully down, negative mouth, open mouth",
    "curious":      "PASS: slightly widened eyes, raised brows — mild interest",
    "embarrassed":  "PASS: reversed brow direction, strained smile",
    # ── Sable expressions ────────────────────────────────────────────────────
    "wry":          "PASS: clear partial smile + brow raise — dry wit. More than neutral, less than happy",
    "grave":        "PASS: eyes fully open (holds gaze), clearly downturned mouth — solemn, not sad",
    "hushed":       "PASS: eyes noticeably hooded vs neutral, mouth neutral/flat — conspiratorial",
    "contemptuous": "PASS: brow furrow + upward mouth — mildly superior smug",
    # ── base reactions ───────────────────────────────────────────────────────
    "idle":         "PASS: visible head drift + breathing — no frozen positions",
    "nod_review":   "INTERNAL TOOL — NOT a nod. 3.5s hold. PASS: smooth return, no snap",
    "nod":          "PASS: smooth dip ~30-35% pitch range + rebound, clean exit",
    "deep_nod":     "PASS: visibly deeper than nod (~50% pitch), smooth exit",
    "look_away":    "PASS: smooth turn, gradual 1.0s return. FAIL: snap at exit",
    "tap":          "PASS: jolt + damped oscillation settling smoothly. FAIL: snap",
    # ── Sable reactions ──────────────────────────────────────────────────────
    "lean_in":      "PASS: very slow 1.2s onset, deep −10° hold, smooth 1s return. No snap",
    "consult":      "PASS: clear +14° tilt + eye drop, smooth return — fadeout guard. No snap, no wobble",
    "glance_down":  "PASS: eyes drop visibly (−0.6), 0.4s hold, smooth 0.8s return. No snap",
    "address":      "PASS: chin-up +6° rise, hold, smooth return. No snap. Ignores head yaw",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def _build_drawtext_filter(behaviors: list, dur: float) -> str:
    parts = []
    for i, b in enumerate(behaviors):
        t0, t1 = i * dur, (i + 1) * dur

        # Bottom overlay: behavior label
        e = _escape_drawtext(b["label"])
        parts.append(
            f"drawtext=text='{e}'"
            f":enable='between(t\\,{t0:.3f}\\,{t1:.3f})'"
            f":fontsize=36:fontcolor=white"
            f":x=(w-tw)/2:y=h-120"
            f":box=1:boxcolor=black@0.65:boxborderw=14"
        )

        # Top overlay: what to look for
        key  = b["cue_value"]
        desc = REVIEW_CRITERIA.get(key, "See authoring notes for review criteria")
        desc_e = _escape_drawtext(desc)
        parts.append(
            f"drawtext=text='{desc_e}'"
            f":enable='between(t\\,{t0:.3f}\\,{t1:.3f})'"
            f":fontsize=24:fontcolor=yellow"
            f":x=(w-tw)/2:y=40"
            f":box=1:boxcolor=black@0.7:boxborderw=10"
        )

    return ",".join(parts)


def _tile_audio(src: Path, dest: Path, total_dur: float) -> None:
    r = subprocess.run(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
         "-t", f"{total_dur:.3f}", "-c", "copy", str(dest)],
        capture_output=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"audio tile failed:\n{r.stderr.decode(errors='replace')}")


def _tile_lipsync(keyframes: list, loop_dur: float, total_dur: float) -> list:
    tiled, i = [], 0
    while (offset := i * loop_dur) < total_dur:
        for kf in keyframes:
            t = round(kf["time"] + offset, 4)
            if t >= total_dur:
                break
            tiled.append({"time": t, "mouth_shape": kf["mouth_shape"]})
        i += 1
    return tiled


def _extract_id(value) -> str:
    return value["id"] if isinstance(value, dict) else value


# ── behavior extraction ───────────────────────────────────────────────────────

def _behaviors_from_registry(model_id: str):
    """Return (behaviors, draft_entry=None) from the registry."""
    with open(REGISTRY_PATH, encoding="utf-8") as fh:
        registry = json.load(fh)

    entry = next((m for m in registry if m["id"] == model_id), None)
    if entry is None:
        ids = [m["id"] for m in registry]
        print(f"ERROR: '{model_id}' not in registry. Available: {ids}", file=sys.stderr)
        sys.exit(1)

    behaviors = []
    for alias, val in entry.get("emotions", {}).items():
        mid = _extract_id(val)
        behaviors.append({
            "cue_key":   "emotion",
            "cue_value": alias,
            "label":     f"{alias}  \u2192  {mid}  (emotion)",
        })
    for alias, val in entry.get("reactions", {}).items():
        mid = _extract_id(val)
        behaviors.append({
            "cue_key":   "reaction",
            "cue_value": alias,
            "label":     f"{alias}  \u2192  {mid}  (reaction)",
        })

    return behaviors, None


def _behaviors_from_model_path(model_path: Path):
    """
    Return (behaviors, draft_entry) from a model3.json directly.
    draft_entry must be temporarily inserted into the registry before rendering.
    """
    if not model_path.exists():
        print(f"ERROR: not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    with open(model_path, encoding="utf-8") as fh:
        model3 = json.load(fh)

    behaviors       = []
    draft_emotions  = {}
    draft_reactions = {}

    for expr in model3.get("FileReferences", {}).get("Expressions", []):
        name = expr.get("Name", "?")
        behaviors.append({
            "cue_key":   "emotion",
            "cue_value": name,
            "label":     f"{name}  (expression)",
        })
        draft_emotions[name] = {"id": name}

    for group_name in model3.get("FileReferences", {}).get("Motions", {}).keys():
        alias = group_name.lower()
        behaviors.append({
            "cue_key":   "reaction",
            "cue_value": alias,
            "label":     f"{group_name}  (motion)",
        })
        draft_reactions[alias] = {"id": group_name}

    rel_path = str(model_path.relative_to(ROOT)).replace("\\", "/")
    draft_entry = {
        "id":        DRAFT_ID,
        "path":      rel_path,
        "emotions":  draft_emotions,
        "reactions": draft_reactions,
    }

    return behaviors, draft_entry


# ── registry draft helpers ────────────────────────────────────────────────────

def _insert_draft(entry: dict) -> None:
    with open(REGISTRY_PATH, encoding="utf-8") as fh:
        registry = json.load(fh)
    registry = [m for m in registry if m["id"] != DRAFT_ID]
    registry.append(entry)
    with open(REGISTRY_PATH, "w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2)


def _remove_draft() -> None:
    with open(REGISTRY_PATH, encoding="utf-8") as fh:
        registry = json.load(fh)
    registry = [m for m in registry if m["id"] != DRAFT_ID]
    with open(REGISTRY_PATH, "w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a behavior review video for a Live2D model."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--model", metavar="ID",
        help="Model ID in registry (post-registration review)",
    )
    group.add_argument(
        "--model-path", metavar="PATH",
        help="Path to .model3.json (onboarding / pre-registration review)",
    )
    parser.add_argument(
        "--duration", type=float, default=None,
        help="Seconds per behavior (default: 3 onboarding, 5 registry)",
    )
    parser.add_argument(
        "--no-lipsync", action="store_true",
        help="Skip lip sync audio",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output path (default: tests/output/<stem>_review.mp4)",
    )
    args = parser.parse_args()

    # ── collect behaviors ──────────────────────────────────────────────────
    onboarding     = args.model_path is not None
    draft_inserted = False

    if onboarding:
        model_path             = (ROOT / args.model_path).resolve()
        behaviors, draft_entry = _behaviors_from_model_path(model_path)
        render_id              = DRAFT_ID
        dur                    = args.duration or 3.0
        out_stem               = model_path.stem
        mode_label             = "onboarding (pre-registration)"
    else:
        behaviors, _ = _behaviors_from_registry(args.model)
        render_id    = args.model
        dur          = args.duration or 5.0
        out_stem     = args.model
        mode_label   = "registry"

    if not behaviors:
        print("ERROR: no behaviors found.", file=sys.stderr)
        sys.exit(1)

    total_dur = dur * len(behaviors)

    print(f"Mode      : {mode_label}")
    print(f"Model     : {render_id}")
    print(f"Behaviors : {len(behaviors)}")
    for b in behaviors:
        print(f"  {b['label']}")
    print(f"Duration  : {dur:.1f}s x {len(behaviors)} = {total_dur:.1f}s total")

    # ── output paths ───────────────────────────────────────────────────────
    out_dir = ROOT / "tests/output"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path      = out_dir / f"{out_stem}_review_raw.mp4"
    final_path    = Path(args.output) if args.output else out_dir / f"{out_stem}_review.mp4"
    manifest_path = out_dir / f"{out_stem}_review_manifest.json"

    # ── lipsync / audio ────────────────────────────────────────────────────
    use_lipsync = (
        not args.no_lipsync
        and TEMPLATE_AUDIO.exists()
        and TEMPLATE_MANIFEST.exists()
    )

    tiled_lipsync    = []
    audio_arg        = None
    tiled_audio_path = None
    tmpl             = {}

    if use_lipsync:
        with open(TEMPLATE_MANIFEST, encoding="utf-8") as fh:
            tmpl = json.load(fh)
        template_lipsync = tmpl.get("lipsync", [])
        max_t    = max((kf["time"] for kf in template_lipsync), default=0.0)
        loop_dur = max_t + 1.0

        tiled_audio_path = out_dir / f"{out_stem}_review_audio.wav"
        print(f"\nTiling audio for {total_dur:.1f}s ...")
        _tile_audio(TEMPLATE_AUDIO, tiled_audio_path, total_dur)

        tiled_lipsync = _tile_lipsync(template_lipsync, loop_dur, total_dur)
        audio_arg     = str(tiled_audio_path).replace("\\", "/")
    else:
        reason = "--no-lipsync" if args.no_lipsync else "template audio not found"
        print(f"Lip sync  : disabled ({reason})")

    # ── build cues ─────────────────────────────────────────────────────────
    cues = []
    for i, b in enumerate(behaviors):
        cues.append({"time": round(i * dur, 3), b["cue_key"]: b["cue_value"]})

    # Terminal hold: ensures renderer produces exactly total_dur frames
    terminal_t = round(total_dur - 1.0, 3)
    if terminal_t > cues[-1]["time"]:
        last = behaviors[-1]
        cues.append({"time": terminal_t, last["cue_key"]: last["cue_value"]})

    # ── write manifest ─────────────────────────────────────────────────────
    manifest = {
        "schema_version": "1.0",
        "model":      {"id": render_id},
        "audio":      audio_arg,
        "output":     str(raw_path).replace("\\", "/"),
        "resolution": tmpl.get("resolution", [1080, 1920]),
        "fps":        tmpl.get("fps", 30),
        "background": "#1a1a2e",
        "lipsync":    tiled_lipsync,
        "cues":       cues,
    }

    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"\nManifest  : {manifest_path}")
    if tiled_lipsync:
        print(f"Lipsync   : {len(tiled_lipsync)} keyframes")

    # ── temporarily register draft (onboarding mode only) ─────────────────
    if onboarding:
        _insert_draft(draft_entry)
        draft_inserted = True

    # ── render ────────────────────────────────────────────────────────────
    import platform
    if platform.system() == "Windows":
        renderer = ROOT / "build/Release/live2d-render.exe"
    else:
        renderer = ROOT / "build/live2d-render"
    if not renderer.exists():
        print(f"ERROR: renderer not found at {renderer}\n"
              f"       Run: cmake --build build --config Release", file=sys.stderr)
        if draft_inserted:
            _remove_draft()
        sys.exit(1)

    print("Rendering ...")
    try:
        result = subprocess.run(
            [str(renderer), "--scene", str(manifest_path)],
            cwd=str(ROOT),
        )
    finally:
        if draft_inserted:
            _remove_draft()
            draft_inserted = False

    if result.returncode != 0:
        print(f"ERROR: renderer exited {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

    if not raw_path.exists():
        print(f"ERROR: expected output not found: {raw_path}", file=sys.stderr)
        sys.exit(1)

    # ── burn labels ────────────────────────────────────────────────────────
    vf = _build_drawtext_filter(behaviors, dur)

    print("Burning labels ...")
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(raw_path),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            *([ "-c:a", "copy"] if use_lipsync else ["-an"]),
            str(final_path),
        ],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print(f"ERROR: ffmpeg label burn exited {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

    # ── cleanup intermediates ──────────────────────────────────────────────
    raw_path.unlink(missing_ok=True)
    if tiled_audio_path:
        tiled_audio_path.unlink(missing_ok=True)

    print(f"\nDone.")
    print(f"  Review   : {final_path}")
    print(f"  Manifest : {manifest_path}")


if __name__ == "__main__":
    main()
