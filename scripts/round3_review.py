#!/usr/bin/env python3
"""
Round 3 targeted review render — majo reactions: nod, look_away, tap.

Renders only the 3 revised reaction clips (Revise verdicts from round 2).
Each clip:
  - 1 second idle baseline (reviewer sees resting state before reaction)
  - Reaction triggered at t=1.0
  - 5+ seconds idle after reaction ends (reviewer sees recovery / breath resumption)
  - FFmpeg text overlay: "<clip_name>  round 3  [REVISED r3]"

Output: results/tests/majo_review/round_3_revised.mp4
Intermediates: results/tests/majo_review/_tmp/

Usage:
    python scripts/round3_review.py
    python scripts/round3_review.py --dry-run   # print manifests, skip render
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── resolve renderer binary ────────────────────────────────────────────────────

def _resolve_renderer() -> Path:
    env_path = ROOT / ".env"
    render_bin = None
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("LIVE2D_RENDER_BIN="):
                val = line.split("=", 1)[1].strip()
                if val:
                    render_bin = Path(val)
                    break
    if render_bin is None:
        render_bin = ROOT / "build/live2d-render"
    if not render_bin.is_absolute():
        render_bin = ROOT / render_bin
    return render_bin


def _ensure_renderer(render_bin: Path) -> None:
    if render_bin.exists():
        return
    print(f"Renderer not found at {render_bin} — building ...")
    r = subprocess.run(
        ["cmake", "--preset", "linux"],
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        print("ERROR: cmake configure failed", file=sys.stderr)
        sys.exit(1)
    r = subprocess.run(
        ["cmake", "--build", "--preset", "linux"],
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        print("ERROR: cmake build failed", file=sys.stderr)
        sys.exit(1)
    if not render_bin.exists():
        print(f"ERROR: build succeeded but binary not found at {render_bin}", file=sys.stderr)
        sys.exit(1)
    # Update .env
    env_path = ROOT / ".env"
    rel = str(render_bin.relative_to(ROOT)).replace("\\", "/")
    env_path.write_text(f"LIVE2D_RENDER_BIN={rel}\n")
    print(f"Built and wrote .env: LIVE2D_RENDER_BIN={rel}")


# ── clip definitions ───────────────────────────────────────────────────────────
#
# Each clip:
#   trigger_time: when to fire the reaction (1.0s gives 1s of idle baseline)
#   reaction_duration: approximate length of the motion file
#   total_duration: trigger_time + reaction_duration + 5s idle buffer
#                   (rounded up to next whole second, minimum 7s)
#
# Sentinel "neutral" cue is placed at trigger_time + reaction_duration to
# ensure the idle buffer is explicit in the manifest.

CLIPS = [
    {
        "name": "nod",
        "reaction": "nod",
        "trigger_time": 1.0,
        "reaction_duration": 1.5,   # nod.motion3.json Duration = 1.5s
        "total_duration": 8.0,      # 1 + 1.5 + 5.5 idle  ≥ 7s minimum
        "label": "nod  round 3  [REVISED r3]",
    },
    {
        "name": "look_away",
        "reaction": "look_away",
        "trigger_time": 1.0,
        "reaction_duration": 1.5,   # look_away.motion3.json Duration = 1.5s
        "total_duration": 8.0,      # 1 + 1.5 + 5.5 idle  ≥ 7s minimum
        "label": "look_away  round 3  [REVISED r3]",
    },
    {
        "name": "tap",
        "reaction": "tap",
        "trigger_time": 1.0,
        "reaction_duration": 0.8,   # tap.motion3.json Duration = 0.8s
        "total_duration": 7.0,      # 1 + 0.8 + 5.2 idle  ≥ 7s minimum
        "label": "tap  round 3  [REVISED r3]",
    },
]

MODEL_ID = "majo"
RESOLUTION = [1280, 720]
FPS = 30


# ── helpers ────────────────────────────────────────────────────────────────────

def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def _drawtext_filter(label: str, duration: float) -> str:
    e = _escape_drawtext(label)
    return (
        f"drawtext=text='{e}'"
        f":enable='between(t\\,0\\,{duration:.3f})'"
        f":fontsize=40:fontcolor=white"
        f":x=(w-tw)/2:y=h-100"
        f":box=1:boxcolor=black@0.65:boxborderw=14"
    )


def _build_manifest(clip: dict, output_path: Path) -> dict:
    trigger = clip["trigger_time"]
    react_end = trigger + clip["reaction_duration"]
    sentinel_time = round(react_end + 0.1, 2)   # just after reaction ends
    total = clip["total_duration"]

    cues = [
        {"time": trigger, "reaction": clip["reaction"]},
        {"time": sentinel_time, "emotion": "neutral"},
    ]

    return {
        "schema_version": "1.0",
        "model": {"id": MODEL_ID},
        "audio": None,
        "output": str(output_path).replace("\\", "/"),
        "resolution": RESOLUTION,
        "fps": FPS,
        "background": "#1a1a2e",
        "duration": total,
        "lipsync": [],
        "cues": cues,
    }


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Round 3 targeted review render for majo revised reactions."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print manifests and FFmpeg commands without rendering.",
    )
    args = parser.parse_args()

    render_bin = _resolve_renderer()
    if not args.dry_run:
        _ensure_renderer(render_bin)

    # ── output dirs ───────────────────────────────────────────────────────
    out_dir = ROOT / "results/tests/majo_review"
    tmp_dir = out_dir / "_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    final_output = out_dir / "round_3_revised.mp4"

    rendered_clips = []   # list of (labeled_path, clip)
    clip_index    = []    # for reporting

    cumulative_offset = 0.0

    for clip in CLIPS:
        raw_path     = tmp_dir / f"round3_{clip['name']}_raw.mp4"
        labeled_path = tmp_dir / f"round3_{clip['name']}_labeled.mp4"
        manifest_path = tmp_dir / f"round3_{clip['name']}_manifest.json"

        manifest = _build_manifest(clip, raw_path)

        if args.dry_run:
            print(f"\n{'='*60}")
            print(f"CLIP: {clip['name']}")
            print(f"Manifest: {manifest_path}")
            print(json.dumps(manifest, indent=2))
        else:
            with open(manifest_path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2)
            print(f"\nRendering clip: {clip['name']} ({clip['total_duration']}s) ...")
            r = subprocess.run(
                [str(render_bin), "--scene", str(manifest_path)],
                cwd=str(ROOT),
            )
            if r.returncode != 0:
                print(f"ERROR: renderer exited {r.returncode} for clip {clip['name']}", file=sys.stderr)
                sys.exit(r.returncode)
            if not raw_path.exists():
                print(f"ERROR: expected output not found: {raw_path}", file=sys.stderr)
                sys.exit(1)

            # burn label
            print(f"Burning label for {clip['name']} ...")
            vf = _drawtext_filter(clip["label"], clip["total_duration"])
            r = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(raw_path),
                    "-vf", vf,
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-an",
                    str(labeled_path),
                ],
                cwd=str(ROOT),
            )
            if r.returncode != 0:
                print(f"ERROR: ffmpeg label burn exited {r.returncode}", file=sys.stderr)
                sys.exit(r.returncode)

            raw_path.unlink(missing_ok=True)

        clip_index.append({
            "clip": clip["name"],
            "label": clip["label"],
            "timestamp_in_output": f"{int(cumulative_offset // 60):02d}:{cumulative_offset % 60:04.1f}",
            "offset_seconds": cumulative_offset,
            "duration_seconds": clip["total_duration"],
        })
        cumulative_offset += clip["total_duration"]
        rendered_clips.append((labeled_path, clip))

    if args.dry_run:
        print("\n\n[DRY RUN] Skipped render and concatenation.")
        print("Clip index (if rendered):")
        for entry in clip_index:
            print(f"  {entry['timestamp_in_output']}  {entry['clip']}  ({entry['duration_seconds']}s)")
        return

    # ── concatenate ───────────────────────────────────────────────────────
    concat_list = tmp_dir / "round3_concat.txt"
    with open(concat_list, "w", encoding="utf-8") as fh:
        for labeled_path, _ in rendered_clips:
            fh.write(f"file '{labeled_path.resolve()}'\n")

    print("\nConcatenating clips ...")
    r = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            "-an",
            str(final_output),
        ],
        cwd=str(ROOT),
    )
    if r.returncode != 0:
        print(f"ERROR: ffmpeg concat exited {r.returncode}", file=sys.stderr)
        sys.exit(r.returncode)

    # ── cleanup intermediates ─────────────────────────────────────────────
    for labeled_path, _ in rendered_clips:
        labeled_path.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)

    # ── report ────────────────────────────────────────────────────────────
    print(f"\nDone.")
    print(f"  Output : {final_output}")
    print(f"\nClip index:")
    for entry in clip_index:
        print(f"  {entry['timestamp_in_output']}  ({entry['offset_seconds']:5.1f}s)  {entry['clip']}  — {entry['label']}")

    # Write clip index JSON alongside the video
    index_path = out_dir / "round_3_clip_index.json"
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(clip_index, fh, indent=2)
    print(f"  Index  : {index_path}")


if __name__ == "__main__":
    main()
