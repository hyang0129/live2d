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
    "consult":      "PASS: clear +14deg tilt + eye drop, smooth return — fade-to-idle exit. No snap, no wobble",
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


# ── animation-state overlay helpers (from consult_review.py pattern) ──────────

STEP = 0.1   # countdown granularity (seconds)


def _esc(s: str) -> str:
    """Escape a string for FFmpeg drawtext text='...' value."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def _between(t0: float, t1: float) -> str:
    """FFmpeg enable expression: active while t0 <= t <= t1."""
    return f"between(t\\,{t0:.3f}\\,{t1:.3f})"


def _dt(text: str, y_from_bottom: int, enable: str = "1",
        color: str = "red", fontsize: int = 21) -> str:
    """Single drawtext filter, anchored to bottom-left at y=h-{y_from_bottom}."""
    return (
        f"drawtext=text='{text}'"
        f":enable='{enable}'"
        f":fontsize={fontsize}:fontcolor={color}"
        f":x=18:y=h-{y_from_bottom}"
        f":box=1:boxcolor=black@0.78:boxborderw=6"
    )


def _seq(text_fn, phase_start: float, phase_end: float,
         y_from_bottom: int, color: str = "red") -> list:
    """
    Generate static drawtext entries at STEP granularity for a phase.
    text_fn(remaining_seconds) -> display string for this interval.
    Avoids FFmpeg's eif 'f' format (not supported in FFmpeg 4.4).
    """
    entries = []
    t = phase_start
    while t < phase_end - 0.001:
        t0  = round(t, 3)
        t1  = round(min(t + STEP, phase_end), 3)
        rem = max(0.0, phase_end - t)
        entries.append(_dt(
            _esc(text_fn(rem)),
            y_from_bottom=y_from_bottom,
            enable=_between(t0, t1),
            color=color,
        ))
        t = round(t + STEP, 3)
    return entries


def _get_motion_dur(model_dir: Path, group_name: str, model3: dict) -> float:
    """
    Read the duration from the motion file for the given group name.
    Returns None if the file cannot be found or read.
    """
    motions = model3.get("FileReferences", {}).get("Motions", {})
    group_motions = motions.get(group_name, [])
    if not group_motions:
        return None
    motion_file_rel = group_motions[0].get("File")
    if not motion_file_rel:
        return None
    motion_path = model_dir / motion_file_rel
    if not motion_path.exists():
        return None
    try:
        with open(motion_path, encoding="utf-8") as fh:
            motion_data = json.load(fh)
        return motion_data.get("Meta", {}).get("Duration")
    except Exception:
        return None


def _build_animation_state_overlays(behaviors: list, dur: float, model_dir: Path, registry_entry: dict) -> list:
    """
    Returns list of drawtext strings for bottom-left animation state display.

    Per-segment overlay rules:

    For emotion segments:
      Line 1 (bottom-left): idle  [looping] — always, red
      Line 2: [emotion_name]  (expression)  :  Xs remaining — red, countdown from dur to 0

    For reaction segments:
      Line 1: idle  [looping] — always, red
      Line 2: [alias]  (playing)  :  Xs remaining — red, from segment start to segment_start + motion_dur
      Line 3 (if fade_to_idle): fade-to-idle  :  Xs remaining — cyan, from motion end to motion end + fade_dur
    """
    LH = 43    # line height including padding (px)
    Y0 = 175   # y-from-bottom for the bottommost left line

    # Load model3.json to get motion file references
    model3_path = model_dir / (model_dir.name + ".model3.json")
    model3 = {}
    if model3_path.exists():
        try:
            with open(model3_path, encoding="utf-8") as fh:
                model3 = json.load(fh)
        except Exception:
            pass

    # Build reactions lookup from registry entry
    reactions_registry = registry_entry.get("reactions", {})

    parts = []
    for i, b in enumerate(behaviors):
        seg_start = i * dur
        seg_end   = seg_start + dur
        cue_key   = b["cue_key"]
        alias     = b["cue_value"]

        # Line 1: idle [looping] — always present for this segment
        parts.append(_dt(
            "idle  [looping]",
            y_from_bottom=Y0,
            enable=_between(seg_start, seg_end),
            color="red",
        ))

        if cue_key == "emotion":
            # Line 2: emotion countdown from seg_start to seg_end
            parts.extend(_seq(
                lambda rem, a=alias: f"{a}  (expression)  :  {rem:.1f}s remaining",
                seg_start, seg_end, Y0 + LH, color="red",
            ))

        elif cue_key == "reaction":
            if alias == "idle":
                # idle loops the whole segment — no Line 2 needed (just idle looping)
                pass
            else:
                # Look up reaction in registry
                reaction_val = reactions_registry.get(alias, {})
                if isinstance(reaction_val, str):
                    # simple string id
                    reaction_val = {"id": reaction_val}

                group_name   = reaction_val.get("id", alias)
                has_fade     = reaction_val.get("fade_to_idle", False)
                fade_dur_cfg = reaction_val.get("fade_to_idle_duration", 0)
                fade_dur     = fade_dur_cfg if (fade_dur_cfg and fade_dur_cfg > 0) else 1.0

                # Get motion duration
                raw_motion_dur = _get_motion_dur(model_dir, group_name, model3)
                if raw_motion_dur is None:
                    # Can't read motion file — treat as filling the whole segment, no fade
                    motion_dur = dur
                    has_fade   = False
                else:
                    motion_dur = min(raw_motion_dur, dur)  # clamp to segment duration

                motion_end = seg_start + motion_dur
                fade_end   = motion_end + (fade_dur if has_fade else 0.0)

                # Line 2: motion playing countdown
                play_end = min(motion_end, seg_end)
                if play_end > seg_start:
                    parts.extend(_seq(
                        lambda rem, a=alias: f"{a}  (playing)  :  {rem:.1f}s remaining",
                        seg_start, play_end, Y0 + LH, color="red",
                    ))

                # Line 3: fade-to-idle countdown (cyan)
                if has_fade and fade_end > motion_end and motion_end < seg_end:
                    actual_fade_end = min(fade_end, seg_end)
                    parts.extend(_seq(
                        lambda rem: f"fade-to-idle  :  {rem:.1f}s remaining",
                        motion_end, actual_fade_end, Y0 + LH * 2, color="cyan",
                    ))

    return parts


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
    """Return (behaviors, registry_entry) from the registry."""
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

    return behaviors, entry


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
        "--reactions-only", action="store_true",
        help="Render only reactions (skip expressions)",
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
    registry_entry = None   # set only in registry mode

    if onboarding:
        model_path             = (ROOT / args.model_path).resolve()
        behaviors, draft_entry = _behaviors_from_model_path(model_path)
        render_id              = DRAFT_ID
        dur                    = args.duration or 3.0
        out_stem               = model_path.stem
        mode_label             = "onboarding (pre-registration)"
        model_dir              = model_path.parent
    else:
        behaviors, registry_entry = _behaviors_from_registry(args.model)
        render_id    = args.model
        dur          = args.duration or 5.0
        out_stem     = args.model
        mode_label   = "registry"
        # Resolve model_dir from registry entry path
        model_path_rel = registry_entry.get("path", "")
        model_dir      = (ROOT / model_path_rel).parent if model_path_rel else None

    if args.reactions_only:
        behaviors = [b for b in behaviors if b["cue_key"] == "reaction"]

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

    # Ensure output directory exists (for --output with subdirs)
    final_path.parent.mkdir(parents=True, exist_ok=True)

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
    vf_parts = [_build_drawtext_filter(behaviors, dur)]

    # Add bottom-left animation state overlays (registry mode only)
    if registry_entry is not None and model_dir is not None:
        anim_overlays = _build_animation_state_overlays(
            behaviors, dur, model_dir, registry_entry
        )
        if anim_overlays:
            vf_parts.extend(anim_overlays)

    vf = ",".join(vf_parts)

    # Write filter to a temp file to avoid ARG_MAX limits on long drawtext chains.
    vf_script_path = out_dir / f"{out_stem}_review_vf.txt"
    vf_script_path.write_text(vf, encoding="utf-8")

    print("Burning labels ...")
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(raw_path),
            "-filter_script:v", str(vf_script_path),
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
    vf_script_path.unlink(missing_ok=True)
    if tiled_audio_path:
        tiled_audio_path.unlink(missing_ok=True)

    print(f"\nDone.")
    print(f"  Review   : {final_path}")
    print(f"  Manifest : {manifest_path}")


if __name__ == "__main__":
    main()
