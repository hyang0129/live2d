#!/usr/bin/env python3
"""
Review render: CubismBreath snap fix — before vs after.

Renders the same nod sequence (3s idle + nod + 8s recovery) with:
  - PRE-FIX  renderer (main branch, no breath guard)
  - POST-FIX renderer (fix/breath-snap-renderer, fade-weight guard)

Then concatenates into a labelled comparison MP4 with per-frame timestamps.
Output: /tmp/breath_snap_review/review_breath_snap.mp4
"""

import json
import subprocess
import sys
from pathlib import Path

RENDERER_PRE  = Path("/tmp/live2d_build_pre/live2d-render")
RENDERER_POST = Path("/tmp/live2d_build_post/live2d-render")
LIVE2D_ROOT   = Path("/workspaces/hub_1/live2d")
OUT_DIR       = Path("/tmp/breath_snap_review")
FINAL         = OUT_DIR / "review_breath_snap.mp4"
TMP_DIR       = OUT_DIR / "_tmp"

RESOLUTION    = [960, 540]
FPS           = 30

NOD_MANIFEST = {
    "schema_version": "1.0",
    "model": {
        "id": "majo",
        "path": "assets/models/majo/majo.model3.json",
    },
    "audio": "",
    "output": "",          # filled in per render
    "resolution": RESOLUTION,
    "fps": FPS,
    "background": "#1a1a2e",
    "lipsync": [],
    "cues": [
        {"time": 0.0,  "emotion": "neutral"},
        {"time": 2.0,  "reaction": "nod_review"},
        {"time": 4.0,  "reaction": "nod_review"},
        {"time": 8.0,  "emotion": "neutral"},
    ],
    "duration": 9.0,
}


def escape_drawtext(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("'",  "\\'")
    text = text.replace(":",  "\\:")
    text = text.replace("[",  "\\[")
    text = text.replace("]",  "\\]")
    return text


def render_clip(renderer: Path, manifest: dict, out_raw: Path) -> tuple[bool, str]:
    manifest_path = TMP_DIR / f"{out_raw.stem}_manifest.json"
    manifest = dict(manifest)
    manifest["output"] = str(out_raw)
    manifest_path.write_text(json.dumps(manifest, indent=2))

    result = subprocess.run(
        [str(renderer), "--scene", str(manifest_path)],
        capture_output=True, text=True,
        cwd=str(LIVE2D_ROOT),
    )
    log = result.stdout + result.stderr
    if result.returncode != 0:
        print(f"  ERROR: renderer exited {result.returncode}", file=sys.stderr)
        print(log, file=sys.stderr)
        return False, log
    return True, log


def annotate_clip(raw_path: Path, out_path: Path, label1: str, label2: str) -> bool:
    h1 = escape_drawtext(label1)
    h2 = escape_drawtext(label2)

    vf_parts = [
        # Dark header bar
        "drawbox=x=0:y=0:w=iw:h=90:color=black@0.8:t=fill",
        # Label 1 (big, centred)
        f"drawtext=text='{h1}'"
        f":fontsize=26:fontcolor=white:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f":x=(w-tw)/2:y=10:box=0",
        # Label 2 (smaller)
        f"drawtext=text='{h2}'"
        f":fontsize=16:fontcolor=white"
        f":x=(w-tw)/2:y=48:box=0",
        # Per-frame timestamp bottom-right
        "drawtext=text='t\\=%{eif\\:t\\:d}.%{eif\\:mod(t*100\\,100)\\:d}s'"
        ":fontsize=24:fontcolor=white"
        ":x=w-tw-16:y=h-44"
        ":box=1:boxcolor=black@0.7:boxborderw=6",
    ]
    vf = ",".join(vf_parts)

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(raw_path),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            "-an",
            str(out_path),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: ffmpeg annotation exited {result.returncode}", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        return False
    return True


def main():
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, path in [("PRE-FIX renderer", RENDERER_PRE),
                       ("POST-FIX renderer", RENDERER_POST)]:
        if not path.exists():
            print(f"ERROR: {name} not found at {path}", file=sys.stderr)
            sys.exit(1)

    clips = [
        {
            "renderer": RENDERER_PRE,
            "raw":      TMP_DIR / "pre_raw.mp4",
            "ann":      TMP_DIR / "pre_ann.mp4",
            "label1":   "PRE-FIX — no breath guard",
            "label2":   "2 nods at t=2.0s+4.5s (15deg, ends at bottom)  |  HEAD SNAP at each exit",
        },
        {
            "renderer": RENDERER_POST,
            "raw":      TMP_DIR / "post_raw.mp4",
            "ann":      TMP_DIR / "post_ann.mp4",
            "label1":   "POST-FIX — fade-weight breath blend",
            "label2":   "2 nods at t=2.0s+4.5s (15deg, ends at bottom)  |  breath FADES back SMOOTHLY",
        },
    ]

    for clip in clips:
        print(f"\nRendering: {clip['label1']} ...")
        ok, log = render_clip(clip["renderer"], NOD_MANIFEST, clip["raw"])
        if not ok:
            sys.exit(1)
        print(f"  raw: {clip['raw']}  ({clip['raw'].stat().st_size // 1024} KB)")

        print(f"  Annotating ...")
        ok = annotate_clip(clip["raw"], clip["ann"], clip["label1"], clip["label2"])
        if not ok:
            sys.exit(1)
        print(f"  annotated: {clip['ann']}")

    # Concatenate
    concat_list = TMP_DIR / "concat.txt"
    with open(concat_list, "w") as fh:
        for clip in clips:
            fh.write(f"file '{clip['ann']}'\n")

    print(f"\nConcatenating into {FINAL} ...")
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
        print(f"ERROR: concat failed: {result.returncode}", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        sys.exit(1)

    size_kb = FINAL.stat().st_size // 1024
    print(f"\nDONE  →  {FINAL}  ({size_kb} KB)")
    print("  Clip 1: PRE-FIX  (head snaps at nod exit)")
    print("  Clip 2: POST-FIX (smooth breath fade-in)")


if __name__ == "__main__":
    main()
