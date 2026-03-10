#!/usr/bin/env python3
"""
Behavior Review Generator

Iterates through every behavior (emotion + reaction) defined for a model
in the registry. The scene_01 audio + lipsync loop continuously for the
entire review so the reviewer can verify lip-sync at any point, while
the behavior (expression/motion) changes every `dur` seconds.

Each segment is labeled in the lower third:

    neutral  ->  F01  (emotion)

Usage
-----
    python scripts/behavior_review.py
    python scripts/behavior_review.py --model haru
    python scripts/behavior_review.py --duration 5
    python scripts/behavior_review.py --output my_review.mp4

Requirements
------------
- build/Release/live2d-render.exe  (already built)
- ffmpeg in PATH
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEMPLATE_AUDIO    = ROOT / "tests/fixtures/cheesetest/wav/scene_01.wav"
TEMPLATE_MANIFEST = ROOT / "tests/fixtures/cheesetest/scene_01_manifest.json"


# ── helpers ───────────────────────────────────────────────────────────────────

def _escape_drawtext(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("'",  "\\'")
    text = text.replace(":",  "\\:")
    return text


def _build_drawtext_filter(behaviors: list, dur: float) -> str:
    parts = []
    for i, (kind, alias, model_id) in enumerate(behaviors):
        t0 = i * dur
        t1 = (i + 1) * dur
        label = _escape_drawtext(f"{alias}  ->  {model_id}  ({kind})")
        parts.append(
            f"drawtext="
            f"text='{label}'"
            f":enable='between(t\\,{t0:.3f}\\,{t1:.3f})'"
            f":fontsize=36"
            f":fontcolor=white"
            f":x=(w-tw)/2"
            f":y=h-120"
            f":box=1"
            f":boxcolor=black@0.65"
            f":boxborderw=14"
        )
    return ",".join(parts)


def _tile_audio(src: Path, dest: Path, total_dur: float) -> None:
    """Loop `src` for exactly `total_dur` seconds → `dest`."""
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(src),
            "-t", f"{total_dur:.3f}",
            "-c", "copy",
            str(dest),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg audio tiling failed:\n"
            f"{result.stderr.decode(errors='replace')}"
        )


def _tile_lipsync(keyframes: list, loop_dur: float, total_dur: float) -> list:
    """
    Repeat `keyframes` (one loop = `loop_dur` seconds) until `total_dur`.
    Keyframes at or beyond `total_dur` are discarded.
    """
    tiled = []
    i = 0
    while True:
        offset = i * loop_dur
        if offset >= total_dur:
            break
        for kf in keyframes:
            t = round(kf["time"] + offset, 4)
            if t >= total_dur:
                break
            tiled.append({"time": t, "mouth_shape": kf["mouth_shape"]})
        i += 1
    return tiled


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a behavior review video for a registered model."
    )
    parser.add_argument(
        "--model", default="shiori",
        help="Model ID in assets/models/registry.json  (default: shiori)",
    )
    parser.add_argument(
        "--duration", type=float, default=5.0,
        help="Seconds per behavior  (default: 5.0)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output path  (default: tests/output/review_<model>.mp4)",
    )
    args = parser.parse_args()

    dur: float = args.duration

    # ── load registry ──────────────────────────────────────────────────────
    with open(ROOT / "assets/models/registry.json", encoding="utf-8") as fh:
        registry: list = json.load(fh)

    model_entry = next((m for m in registry if m["id"] == args.model), None)
    if model_entry is None:
        ids = [m["id"] for m in registry]
        print(f"ERROR: model '{args.model}' not in registry. Available: {ids}",
              file=sys.stderr)
        sys.exit(1)

    # ── collect behaviors ──────────────────────────────────────────────────
    def _extract_id(value) -> str:
        """Registry values may be a plain string or {"id": "...", "note": "..."}."""
        return value["id"] if isinstance(value, dict) else value

    behaviors: list[tuple[str, str, str]] = []
    for alias, value in model_entry.get("emotions", {}).items():
        behaviors.append(("emotion", alias, _extract_id(value)))
    for alias, value in model_entry.get("reactions", {}).items():
        behaviors.append(("reaction", alias, _extract_id(value)))

    if not behaviors:
        print(f"ERROR: no behaviors defined for '{args.model}' in registry.",
              file=sys.stderr)
        sys.exit(1)

    print(f"Model     : {args.model}  ({model_entry['path']})")
    print(f"Behaviors : {len(behaviors)}")
    for kind, alias, mid in behaviors:
        print(f"  {kind:8s}  {alias:18s}  ->  {mid}")

    total_dur = dur * len(behaviors)
    print(f"\nDuration  : {dur:.1f}s × {len(behaviors)} behaviors = {total_dur:.1f}s total")

    # ── load template ──────────────────────────────────────────────────────
    with open(TEMPLATE_MANIFEST, encoding="utf-8") as fh:
        template: dict = json.load(fh)

    template_lipsync: list[dict] = template.get("lipsync", [])

    # Period of one lipsync loop: last keyframe time + 1 s tail
    # (mirrors the renderer's own duration formula so loop boundaries are clean)
    max_lipsync_t = max((kf["time"] for kf in template_lipsync), default=0.0)
    loop_dur = max_lipsync_t + 1.0

    # ── output paths ──────────────────────────────────────────────────────
    out_dir = ROOT / "tests/output"
    out_dir.mkdir(parents=True, exist_ok=True)

    tiled_audio_path = out_dir / f"review_{args.model}_audio.wav"
    raw_path         = out_dir / f"review_{args.model}_raw.mp4"
    final_path       = (Path(args.output) if args.output
                        else out_dir / f"review_{args.model}.mp4")
    manifest_path    = out_dir / f"review_{args.model}_manifest.json"

    # ── tile audio ────────────────────────────────────────────────────────
    if not TEMPLATE_AUDIO.exists():
        print(f"ERROR: template audio not found: {TEMPLATE_AUDIO}", file=sys.stderr)
        sys.exit(1)

    print(f"\nTiling audio for {total_dur:.1f}s …")
    _tile_audio(TEMPLATE_AUDIO, tiled_audio_path, total_dur)

    # ── tile lipsync ──────────────────────────────────────────────────────
    tiled_lipsync = _tile_lipsync(template_lipsync, loop_dur, total_dur)

    # ── behavior cues ─────────────────────────────────────────────────────
    cues = []
    for i, (kind, alias, _) in enumerate(behaviors):
        t = round(i * dur, 3)
        key = "emotion" if kind == "emotion" else "reaction"
        cues.append({"time": t, key: alias})

    # Terminal hold cue so the renderer produces exactly total_dur frames.
    # Renderer formula: scene_duration = max(last_cue, last_lipsync) + 1 s
    # → set last_cue = total_dur - 1.0 so scene_duration = total_dur.
    terminal_t = round(total_dur - 1.0, 3)
    if terminal_t > cues[-1]["time"]:
        last_kind, last_alias, _ = behaviors[-1]
        key = "emotion" if last_kind == "emotion" else "reaction"
        cues.append({"time": terminal_t, key: last_alias})

    # ── write manifest ────────────────────────────────────────────────────
    manifest = {
        "schema_version": "1.0",
        "model":      template["model"],
        "audio":      str(tiled_audio_path).replace("\\", "/"),
        "output":     str(raw_path).replace("\\", "/"),
        "resolution": template["resolution"],
        "fps":        template["fps"],
        "background": "#1a1a2e",
        "lipsync":    tiled_lipsync,
        "cues":       cues,
    }

    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"Manifest   : {manifest_path}")
    print(f"Lipsync    : {len(tiled_lipsync)} keyframes "
          f"({len(template_lipsync)} × ~{total_dur / loop_dur:.1f} loops)")

    # ── render ────────────────────────────────────────────────────────────
    renderer = ROOT / "build/Release/live2d-render.exe"
    if not renderer.exists():
        print(f"ERROR: renderer not found at {renderer}\n"
              f"       Run: cmake --build build --config Release",
              file=sys.stderr)
        sys.exit(1)

    print(f"\nRendering …")
    result = subprocess.run(
        [str(renderer), "--scene", str(manifest_path)],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print(f"ERROR: renderer exited {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

    if not raw_path.exists():
        print(f"ERROR: expected output not found: {raw_path}", file=sys.stderr)
        sys.exit(1)

    # ── burn labels ───────────────────────────────────────────────────────
    vf = _build_drawtext_filter(behaviors, dur)

    print("Burning labels …")
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(raw_path),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(final_path),
        ],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print(f"ERROR: ffmpeg label burn exited {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

    # ── clean up intermediates ────────────────────────────────────────────
    raw_path.unlink(missing_ok=True)
    tiled_audio_path.unlink(missing_ok=True)

    print(f"\nDone.")
    print(f"  Review video : {final_path}")
    print(f"  Manifest     : {manifest_path}")
    print()
    print("Behavior map:")
    for kind, alias, mid in behaviors:
        print(f"  {alias:18s}  ->  {mid:10s}  ({kind})")


if __name__ == "__main__":
    main()
