#!/usr/bin/env python3
"""
Review render: Motion entry validation — none vs implicit normalisation.

Renders the same nod cue (triggered at t=2.0s, near peak breath yaw) with:
  - NONE     (out_of_range_mode: none)    — nod fires immediately while head is
             tilted ~+14° right from breath. Motion reads poorly.
  - IMPLICIT (out_of_range_mode: implicit) — renderer normalises AngleX to ±5°
             first (~0.6s), then nod fires. Sequence reads cleanly.

Breath profile: AngleX ±15° @ 6.53s period. AngleX ≈ +14.1° at t=2.0s.
Nod cue at t=2.0s (same as breath_guard_review) fires when head is tilted ~+14°,
producing a clear contrast between the two modes.

Output: /tmp/entry_validation_review/review_entry_validation.mp4
"""

import json
import subprocess
import sys
from pathlib import Path

LIVE2D_ROOT = Path("/workspaces/hub_1/live2d")
OUT_DIR     = LIVE2D_ROOT / "results/tests/entry_validation_review"
FINAL       = OUT_DIR / "review_entry_validation.mp4"
TMP_DIR     = OUT_DIR / "_tmp"

# Resolve renderer binary: .env > platform default (per CLAUDE.md auto-build convention)
def _resolve_renderer() -> Path:
    env_file = LIVE2D_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("LIVE2D_RENDER_BIN="):
                p = Path(line.split("=", 1)[1].strip())
                return p if p.is_absolute() else LIVE2D_ROOT / p
    return LIVE2D_ROOT / "build/live2d-render"

RENDERER = _resolve_renderer()

RESOLUTION  = [960, 540]
FPS         = 30

# Nod fires at t=2.0s (AngleX ≈ +14.1° from breath sine; 15*sin(2π*2.0/6.5345)).
# Same timing as breath_guard_review for consistency.
# Scene runs to 9s (sentinel at t=8.0 + 1s render_loop tail),
# satisfying the 5s-minimum + 5s-buffer-after-last-action convention.
BASE_MANIFEST = {
    "schema_version": "1.0",
    "audio": "",
    "output": "",          # filled per render
    "resolution": RESOLUTION,
    "fps": FPS,
    "background": "#1a1a2e",
    "lipsync": [],
    # Nod cue at t=2.0s (AngleX ≈ +14° from breath — outside valid ±5° range).
    # Sentinel cue at t=8.0s extends scene to 9s (8.0 + 1s render_loop tail),
    # satisfying the 5s-minimum + 5s-buffer-after-last-action convention.
    "cues": [
        {"time": 0.0, "emotion": "neutral"},
        {"time": 2.0, "reaction": "nod"},
        {"time": 8.0, "emotion": "neutral"},
    ],
}


def escape_drawtext(text: str) -> str:
    for ch, esc in [("\\", "\\\\"), ("'", "\\'"), (":", "\\:"),
                    ("[", "\\["), ("]", "\\]")]:
        text = text.replace(ch, esc)
    return text


def render_clip(model_id: str, out_raw: Path) -> tuple[bool, str]:
    manifest = dict(BASE_MANIFEST)
    manifest["model"] = {"id": model_id}
    manifest["output"] = str(out_raw)

    manifest_path = TMP_DIR / f"{out_raw.stem}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    result = subprocess.run(
        [str(RENDERER), "--scene", str(manifest_path)],
        capture_output=True, text=True,
        cwd=str(LIVE2D_ROOT),
    )
    log = result.stdout + result.stderr
    if result.returncode != 0:
        print(f"  ERROR: renderer exited {result.returncode}", file=sys.stderr)
        print(log, file=sys.stderr)
        return False, log
    return True, log


def annotate_clip(raw: Path, out: Path, label1: str, label2: str) -> bool:
    h1 = escape_drawtext(label1)
    h2 = escape_drawtext(label2)

    vf = ",".join([
        "drawbox=x=0:y=0:w=iw:h=90:color=black@0.8:t=fill",
        f"drawtext=text='{h1}'"
        f":fontsize=26:fontcolor=white"
        f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f":x=(w-tw)/2:y=10:box=0",
        f"drawtext=text='{h2}'"
        f":fontsize=16:fontcolor=white"
        f":x=(w-tw)/2:y=48:box=0",
        "drawtext=text='t\\=%{eif\\:t\\:d}.%{eif\\:mod(t*100\\,100)\\:d}s'"
        ":fontsize=24:fontcolor=white"
        ":x=w-tw-16:y=h-44"
        ":box=1:boxcolor=black@0.7:boxborderw=6",
        # Marker line at t=2.0s — vertical red line for 1 frame per second, drawn
        # only at the trigger frame using an overlay with enable expression.
        "drawbox=x=iw/2-2:y=90:w=4:h=ih-90:color=red@0.6:t=fill"
        ":enable='between(t,1.97,2.03)'",
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
        print(f"  ERROR: ffmpeg annotation failed", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        return False
    return True


def main():
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not RENDERER.exists():
        print(f"ERROR: renderer not found at {RENDERER}", file=sys.stderr)
        print("Build the renderer and place it at the path above, then re-run.", file=sys.stderr)
        sys.exit(1)

    clips = [
        {
            "model_id": "majo_nod_nocheck",
            "raw":      TMP_DIR / "none_raw.mp4",
            "ann":      TMP_DIR / "none_ann.mp4",
            "label1":   "out_of_range_mode: none  —  no entry check",
            "label2":   "nod at t=2.0s  |  head tilted ~+14° right  |  motion reads POORLY",
        },
        {
            "model_id": "majo",
            "raw":      TMP_DIR / "implicit_raw.mp4",
            "ann":      TMP_DIR / "implicit_ann.mp4",
            "label1":   "out_of_range_mode: implicit  —  normalise-then-play",
            "label2":   "nod at t=2.0s  |  AngleX centres first (~0.6s)  |  nod reads CLEANLY",
        },
    ]

    for clip in clips:
        print(f"\nRendering [{clip['model_id']}] ...")
        ok, log = render_clip(clip["model_id"], clip["raw"])
        if not ok:
            sys.exit(1)
        size_kb = clip["raw"].stat().st_size // 1024
        print(f"  raw: {clip['raw']}  ({size_kb} KB)")

        print(f"  Annotating ...")
        ok = annotate_clip(clip["raw"], clip["ann"], clip["label1"], clip["label2"])
        if not ok:
            sys.exit(1)
        print(f"  annotated: {clip['ann']}")

    concat_list = TMP_DIR / "concat.txt"
    with open(concat_list, "w") as fh:
        for clip in clips:
            fh.write(f"file '{clip['ann']}'\n")

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
        print(f"ERROR: concat failed", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        sys.exit(1)

    size_kb = FINAL.stat().st_size // 1024
    print(f"\nDONE  →  {FINAL}  ({size_kb} KB)")
    print("  Clip 1: none     — nod fires while head tilted right (bad entry)")
    print("  Clip 2: implicit — head normalises to centre first, then nod")
    print()
    print("What to look for:")
    print("  Red marker at t=2.0s = nod cue fires")
    print("  Clip 1: nod starts immediately from ~+14° yaw — appears sideways/wrong")
    print("  Clip 2: head smoothly moves rightward tilt → centre (~0.6s), THEN nod fires")
    print("          Breath guard holds throughout normalisation + nod, fades after")


if __name__ == "__main__":
    main()
