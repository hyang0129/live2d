#!/usr/bin/env python3
"""
Phase C1 — Full Behaviour Review Render (Round 1)
Renders all majo expressions and reactions, annotates, and concatenates.
"""

import json
import subprocess
import sys
import shutil
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT     = Path("/workspaces/hub_1/live2d")
RENDERER = Path("/tmp/live2d_build/live2d-render")
OUT_DIR  = ROOT / "tests/fixtures/majo_review"
TMP_DIR  = OUT_DIR / "_tmp_clips"
FINAL    = OUT_DIR / "round_1_review.mp4"
MANIFEST_OUT = OUT_DIR / "round_1_manifest.json"

# ── clip definitions ───────────────────────────────────────────────────────────
# Each entry: (label_for_human, cue_key, cue_value, clip_duration_s)
CLIPS = [
    # Expressions — 3s each (full fade-in visible)
    ("EXPRESSION: neutral",     "emotion",  "neutral",    3.0),
    ("EXPRESSION: happy",       "emotion",  "happy",      3.0),
    ("EXPRESSION: surprised",   "emotion",  "surprised",  3.0),
    ("EXPRESSION: bored",       "emotion",  "bored",      3.0),
    ("EXPRESSION: sad",         "emotion",  "sad",        3.0),
    ("EXPRESSION: angry",       "emotion",  "angry",      3.0),
    ("EXPRESSION: curious",     "emotion",  "curious",    3.0),
    ("EXPRESSION: embarrassed", "emotion",  "embarrassed",3.0),
    # Reactions — full motion duration + settle time
    ("REACTION: idle",          "reaction", "idle",       3.0),   # ~3s idle loop
    ("REACTION: nod",           "reaction", "nod",        2.0),   # 0.5s motion + 1.5s settle
    ("REACTION: look_away",     "reaction", "look_away",  3.0),   # 1.5s motion + 1.5s settle
    ("REACTION: tap",           "reaction", "tap",        2.5),   # 1.0s motion + 1.5s settle
]

TOTAL_CLIPS = len(CLIPS)


def escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def render_clip(clip_idx: int, label: str, cue_key: str, cue_value: str,
                dur: float, raw_path: Path) -> bool:
    """Write manifest and render one raw clip. Returns True on success."""
    manifest = {
        "schema_version": "1.0",
        "model": {"id": "majo"},
        "audio": None,
        "output": str(raw_path.relative_to(ROOT)),
        "resolution": [1280, 720],
        "fps": 30,
        "background": "#1a1a2e",
        "lipsync": [],
        "cues": [
            {"time": 0.0, cue_key: cue_value},
            # Terminal hold to ensure renderer produces full duration
            {"time": round(dur - 0.5, 3), cue_key: cue_value},
        ],
    }

    manifest_path = TMP_DIR / f"clip_{clip_idx:02d}_manifest.json"
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"  Rendering [{clip_idx+1}/{TOTAL_CLIPS}] {label} ({dur}s) ...")
    result = subprocess.run(
        [str(RENDERER), "--scene", str(manifest_path.relative_to(ROOT))],
        cwd=str(ROOT),
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: renderer exited {result.returncode}", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        return False
    if not raw_path.exists():
        print(f"  ERROR: output not produced: {raw_path}", file=sys.stderr)
        return False
    return True


def annotate_clip(clip_idx: int, label: str, raw_path: Path,
                  annotated_path: Path) -> bool:
    """
    Burn per-clip annotations onto a raw clip:
      - Title bar (top ~110px): line 1 = persistent header, line 2 = clip label
      - Timestamp bottom-right: t=X.XXs
      - Clip index bottom-left: [N/12]
    """
    label_esc  = escape_drawtext(label)
    header_esc = escape_drawtext("MAJO BEHAVIOUR REVIEW — ROUND 1")
    index_str  = escape_drawtext(f"[{clip_idx+1}/{TOTAL_CLIPS}]")

    # Semi-transparent black title bar (top 110px)
    # Using a drawbox + two drawtext lines
    vf_parts = [
        # Title bar background box
        "drawbox=x=0:y=0:w=iw:h=110:color=black@0.7:t=fill",

        # Line 1: persistent header (centred, y=18)
        f"drawtext=text='{header_esc}'"
        f":fontsize=30:fontcolor=white"
        f":x=(w-tw)/2:y=18"
        f":box=0",

        # Line 2: clip-specific label (centred, y=68)
        f"drawtext=text='{label_esc}'"
        f":fontsize=34:fontcolor=yellow"
        f":x=(w-tw)/2:y=68"
        f":box=0",

        # Timestamp bottom-right (B3 compound expression)
        "drawtext=text='t\\=%{eif\\:t\\:d}.%{eif\\:mod(t*100\\,100)\\:d}s'"
        ":fontsize=28:fontcolor=white"
        ":x=w-tw-20:y=h-50"
        ":box=1:boxcolor=black@0.7:boxborderw=8",

        # Clip index bottom-left
        f"drawtext=text='{index_str}'"
        f":fontsize=28:fontcolor=white"
        f":x=20:y=h-50"
        f":box=1:boxcolor=black@0.7:boxborderw=8",
    ]

    vf = ",".join(vf_parts)

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(raw_path),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            "-an",
            str(annotated_path),
        ],
        cwd=str(ROOT),
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: ffmpeg annotation exited {result.returncode}", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        return False
    return True


def get_video_duration(path: Path) -> float:
    """Return duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration",
         "-of", "default=noprint_wrappers=1:nokey=1",
         str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def main():
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    rendered_clips = []   # (label, annotated_path, actual_duration)
    failed_clips   = []

    for i, (label, cue_key, cue_value, dur) in enumerate(CLIPS):
        raw_path        = TMP_DIR / f"clip_{i:02d}_raw.mp4"
        annotated_path  = TMP_DIR / f"clip_{i:02d}_annotated.mp4"

        ok = render_clip(i, label, cue_key, cue_value, dur, raw_path)
        if not ok:
            failed_clips.append((label, "render failed"))
            continue

        ok = annotate_clip(i, label, raw_path, annotated_path)
        if not ok:
            failed_clips.append((label, "annotation failed"))
            continue

        actual_dur = get_video_duration(annotated_path)
        rendered_clips.append((label, annotated_path, actual_dur))
        print(f"  OK: {label} — {actual_dur:.2f}s actual")

    if not rendered_clips:
        print("ERROR: No clips rendered successfully.", file=sys.stderr)
        sys.exit(1)

    # ── concatenate ────────────────────────────────────────────────────────────
    concat_list = TMP_DIR / "concat.txt"
    with open(concat_list, "w") as fh:
        for _, ap, _ in rendered_clips:
            fh.write(f"file '{ap}'\n")

    print("\nConcatenating clips ...")
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(FINAL),
        ],
        cwd=str(ROOT),
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"ERROR: ffmpeg concat exited {result.returncode}", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        sys.exit(result.returncode)

    # ── build round_1_manifest.json ────────────────────────────────────────────
    manifest_clips = []
    cursor = 0.0
    for label, _, actual_dur in rendered_clips:
        manifest_clips.append({
            "label":      label,
            "start_time": round(cursor, 3),
            "duration":   round(actual_dur, 3),
        })
        cursor += actual_dur

    total_dur = cursor
    output_manifest = {
        "video":        str(FINAL),
        "total_duration": round(total_dur, 3),
        "clips":        manifest_clips,
    }
    with open(MANIFEST_OUT, "w") as fh:
        json.dump(output_manifest, fh, indent=2)

    # ── report ─────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"DONE")
    print(f"  Output  : {FINAL}")
    print(f"  Manifest: {MANIFEST_OUT}")
    print(f"  Total   : {total_dur:.2f}s  ({len(rendered_clips)}/{TOTAL_CLIPS} clips)")
    print()
    print("Clips:")
    for c in manifest_clips:
        print(f"  t={c['start_time']:6.2f}s  {c['duration']:.2f}s  {c['label']}")

    if failed_clips:
        print(f"\nFailed clips ({len(failed_clips)}):")
        for label, reason in failed_clips:
            print(f"  {label}: {reason}")

    # Cleanup tmp
    shutil.rmtree(TMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
