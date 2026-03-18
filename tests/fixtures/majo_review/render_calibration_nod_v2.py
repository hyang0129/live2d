#!/usr/bin/env python3
"""
Render calibration_nod_v2.mp4 — single nod clip with AngleY remap annotation.

Clip: nod (12s)
  - 3s idle baseline (emotion=neutral, reaction=idle)
  - nod reaction fires at t=3.0s
  - 8s recovery tail (total 12s)

Annotations:
  Header line 1: MAJO CALIBRATION — NOD (AngleY remap)
  Header line 2: NOD fires at t=3.0s. Should be a head turn/dip using AngleY.
                 AngleX and AngleZ held at 0. 3s idle baseline shown first.
  Bottom-right:  t=X.XXs timestamp
  Bottom-left:   [1/1]
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT     = Path("/workspaces/hub_1/live2d")
RENDERER = Path("/tmp/live2d_build/live2d-render")
OUT_DIR  = ROOT / "tests/fixtures/majo_review"
TMP_DIR  = OUT_DIR / "_tmp_calibration"
OUT_FILE = OUT_DIR / "calibration_nod_v2.mp4"

HEADER_LINE1 = "MAJO CALIBRATION — NOD (AngleY remap)"
HEADER_LINE2 = (
    "NOD fires at t=3.0s. Should be a head turn/dip using AngleY. "
    "AngleX and AngleZ held at 0. 3s idle baseline shown first."
)


def escape_drawtext(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("'",  "\\'")
    text = text.replace(":",  "\\:")
    text = text.replace("[",  "\\[")
    text = text.replace("]",  "\\]")
    return text


def render_raw(raw_path: Path) -> tuple[bool, str]:
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
            {"time":  0.0, "emotion":  "neutral"},
            {"time":  0.0, "reaction": "idle"},
            {"time":  3.0, "reaction": "nod"},
            {"time": 11.0, "reaction": "idle"},  # terminal hold to 12s
        ],
    }

    manifest_path = TMP_DIR / "nod_v2_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print("  Rendering nod clip (12s) ...")
    result = subprocess.run(
        [str(RENDERER), "--scene", str(manifest_path.relative_to(ROOT))],
        cwd=str(ROOT),
        capture_output=True,
    )

    log = result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace")

    if result.returncode != 0:
        print(f"  ERROR: renderer exited {result.returncode}", file=sys.stderr)
        print(log, file=sys.stderr)
        return False, log

    if not raw_path.exists():
        print(f"  ERROR: output not produced: {raw_path}", file=sys.stderr)
        return False, log

    return True, log


def annotate(raw_path: Path, out_path: Path) -> bool:
    h1_esc  = escape_drawtext(HEADER_LINE1)
    h2_esc  = escape_drawtext(HEADER_LINE2)
    idx_str = escape_drawtext("[1/1]")

    vf_parts = [
        # Black header bar 110px
        "drawbox=x=0:y=0:w=iw:h=110:color=black@0.7:t=fill",

        # Line 1: main header, bold white ~28pt, y=12
        f"drawtext=text='{h1_esc}'"
        f":fontsize=28:fontcolor=white"
        f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f":x=(w-tw)/2:y=12:box=0",

        # Line 2: description, white ~18pt, y=52
        f"drawtext=text='{h2_esc}'"
        f":fontsize=18:fontcolor=white"
        f":x=(w-tw)/2:y=52:box=0",

        # Timestamp bottom-right: t=X.XXs
        "drawtext=text='t\\=%{eif\\:t\\:d}.%{eif\\:mod(t*100\\,100)\\:d}s'"
        ":fontsize=28:fontcolor=white"
        ":x=w-tw-20:y=h-50"
        ":box=1:boxcolor=black@0.7:boxborderw=8",

        # Clip index bottom-left: [1/1]
        f"drawtext=text='{idx_str}'"
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
            str(out_path),
        ],
        cwd=str(ROOT),
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: ffmpeg annotation exited {result.returncode}", file=sys.stderr)
        print(result.stderr.decode(errors="replace"), file=sys.stderr)
        return False
    return True


def get_duration(path: Path) -> float:
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


def extract_nod_log_lines(log: str) -> list[str]:
    keywords = [
        'reaction → "nod"',
        'reaction "nod"',
        "TriggerMotion",
        "Cue t=",
        "not found",
        "skipped",
        "warn",
        "WARN",
    ]
    lines = []
    for line in log.splitlines():
        if any(kw.lower() in line.lower() for kw in keywords):
            lines.append(line)
    return lines


def main():
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not RENDERER.exists():
        print(f"ERROR: renderer not found at {RENDERER}", file=sys.stderr)
        sys.exit(1)

    raw_path = TMP_DIR / "nod_v2_raw.mp4"

    ok, log = render_raw(raw_path)
    if not ok:
        sys.exit(1)

    # Save raw log
    log_path = TMP_DIR / "nod_v2_raw.log"
    log_path.write_text(log)

    ok = annotate(raw_path, OUT_FILE)
    if not ok:
        sys.exit(1)

    dur  = get_duration(OUT_FILE)
    size = OUT_FILE.stat().st_size

    print(f"\n{'='*70}")
    print("DONE — calibration_nod_v2.mp4")
    print(f"  Output   : {OUT_FILE}")
    print(f"  Size     : {size} bytes  ({size // 1024} KB)")
    print(f"  Duration : {dur:.2f}s")

    # Log confirmation
    relevant = extract_nod_log_lines(log)
    if relevant:
        print("\nRenderer log — nod-relevant lines:")
        for ln in relevant:
            print(f"  {ln}")
    else:
        print("\n[no nod-specific log lines matched; printing first 50 lines]")
        for ln in log.splitlines()[:50]:
            print(f"  {ln}")


if __name__ == "__main__":
    main()
