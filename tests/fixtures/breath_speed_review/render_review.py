#!/usr/bin/env python3
"""
Review render: Breath speed comparison — 1×, 2×, 3× natural speed.

Renders three side-by-side idle clips at different breath_speed multipliers
so a human reviewer can judge at what speed the idle animation starts to feel
unnatural or anxious.

Breath base period: 6.5345s (AngleX ±7.5°).
  1× → period 6.53s  (~0.15 cycles/s)  — reference
  2× → period 3.27s  (~0.31 cycles/s)
  3× → period 2.18s  (~0.46 cycles/s)

Each clip is 14 seconds (2+ full cycles at 1× speed, 4+ at 2×, 6+ at 3×).

Output: results/tests/breath_speed_review/review_breath_speed.mp4
"""

import json
import subprocess
import sys
from pathlib import Path

LIVE2D_ROOT = Path("/workspaces/hub_1/live2d")
OUT_DIR     = LIVE2D_ROOT / "results/tests/breath_speed_review"
FINAL       = OUT_DIR / "review_breath_speed.mp4"
TMP_DIR     = OUT_DIR / "_tmp"

def _resolve_renderer() -> Path:
    env_file = LIVE2D_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("LIVE2D_RENDER_BIN="):
                p = Path(line.split("=", 1)[1].strip())
                return p if p.is_absolute() else LIVE2D_ROOT / p
    return LIVE2D_ROOT / "build/live2d-render"

RENDERER   = _resolve_renderer()
RESOLUTION = [960, 540]
FPS        = 30

# 14-second idle: sentinel at t=13 + 1s render_loop tail
# No reaction cues — pure idle breath comparison
BASE_MANIFEST = {
    "schema_version": "1.0",
    "model": {"id": "majo"},
    "audio": "",
    "output": "",       # filled per render
    "resolution": RESOLUTION,
    "fps": FPS,
    "background": "#1a1a2e",
    "lipsync": [],
    "cues": [
        {"time": 0.0,  "emotion": "neutral"},
        {"time": 13.0, "emotion": "neutral"},  # sentinel: extends scene to 14s
    ],
    # breath_speed filled per render
}

CLIPS = [
    {"speed": 1.0, "stem": "1x",  "label": "1× speed  (6.53s period)  — reference"},
    {"speed": 2.0, "stem": "2x",  "label": "2× speed  (3.27s period)"},
    {"speed": 3.0, "stem": "3x",  "label": "3× speed  (2.18s period)"},
]


def escape_drawtext(text: str) -> str:
    for ch, esc in [("\\", "\\\\"), ("'", "\\'"), (":", "\\:"),
                    ("[", "\\["), ("]", "\\]")]:
        text = text.replace(ch, esc)
    return text


def render_clip(speed: float, stem: str) -> tuple[bool, Path]:
    raw = TMP_DIR / f"{stem}_raw.mp4"
    manifest = dict(BASE_MANIFEST)
    manifest["output"]       = str(raw)
    manifest["breath_speed"] = speed

    mpath = TMP_DIR / f"{stem}_manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2))

    result = subprocess.run(
        [str(RENDERER), "--scene", str(mpath)],
        capture_output=True, text=True,
        cwd=str(LIVE2D_ROOT),
    )
    log = result.stdout + result.stderr
    if result.returncode != 0:
        print(f"  ERROR: renderer exited {result.returncode}", file=sys.stderr)
        print(log, file=sys.stderr)
        return False, raw
    return True, raw


def annotate_clip(raw: Path, out: Path, label: str, speed: float) -> bool:
    period = 6.5345 / speed
    sub = escape_drawtext(f"period {period:.2f}s  |  {speed:.0f}× natural breath speed")
    lbl = escape_drawtext(label)

    vf = ",".join([
        "drawbox=x=0:y=0:w=iw:h=80:color=black@0.8:t=fill",
        f"drawtext=text='{lbl}'"
        f":fontsize=22:fontcolor=white"
        f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f":x=(w-tw)/2:y=10:box=0",
        f"drawtext=text='{sub}'"
        f":fontsize=16:fontcolor=#aaaaaa"
        f":x=(w-tw)/2:y=44:box=0",
        "drawtext=text='t\\=%{eif\\:t\\:d}.%{eif\\:mod(t*100\\,100)\\:d}s'"
        ":fontsize=22:fontcolor=white"
        ":x=w-tw-16:y=h-40"
        ":box=1:boxcolor=black@0.7:boxborderw=6",
    ])

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(raw),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            "-an",
            str(out),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("  ERROR: ffmpeg annotation failed", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        return False
    return True


def main():
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not RENDERER.exists():
        print(f"ERROR: renderer not found at {RENDERER}", file=sys.stderr)
        sys.exit(1)

    ann_clips = []
    for clip in CLIPS:
        print(f"\nRendering [{clip['stem']}] breath_speed={clip['speed']} ...")
        ok, raw = render_clip(clip["speed"], clip["stem"])
        if not ok:
            sys.exit(1)
        size_kb = raw.stat().st_size // 1024
        print(f"  raw: {raw}  ({size_kb} KB)")

        ann = TMP_DIR / f"{clip['stem']}_ann.mp4"
        print(f"  Annotating ...")
        if not annotate_clip(raw, ann, clip["label"], clip["speed"]):
            sys.exit(1)
        print(f"  annotated: {ann}")
        ann_clips.append(ann)

    # Concatenate
    concat_list = TMP_DIR / "concat.txt"
    with open(concat_list, "w") as fh:
        for ann in ann_clips:
            fh.write(f"file '{ann}'\n")

    print(f"\nConcatenating → {FINAL} ...")
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(FINAL),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print("ERROR: concat failed", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        sys.exit(1)

    size_kb = FINAL.stat().st_size // 1024
    print(f"\nDONE  →  {FINAL}  ({size_kb} KB)")
    print()
    print("What to look for:")
    print("  Judge at what speed the head movement starts to feel anxious/unnatural.")
    print("  Clip 1 (1×): reference natural breathing, ~6.5s full cycle")
    print("  Clip 2 (2×): double speed, ~3.3s cycle — still plausible?")
    print("  Clip 3 (3×): triple speed, ~2.2s cycle — likely noticeably unnatural")


if __name__ == "__main__":
    main()
