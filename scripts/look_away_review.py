#!/usr/bin/env python3
"""
look_away exit-snap review.

Renders look_away on majo at three idle entry points to show the snap
(or lack thereof) when the motion ends and idle breath resumes.

  Clip A — fire at t=2.0 (breath near neutral, best-case)
  Clip B — fire at t=3.27 (≈ AngleX negative peak, worst-case)
  Clip C — fire at t=0.5  (mid-rise, intermediate case)

Output:
  results/tests/look_away_review/review_look_away.mp4
  results/tests/look_away_review/_tmp/
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT  = Path(__file__).resolve().parent.parent
RENDERER   = REPO_ROOT / "build" / "live2d-render"
OUT_DIR    = REPO_ROOT / "results" / "tests" / "look_away_review"
TMP_DIR    = OUT_DIR / "_tmp"
FINAL      = OUT_DIR / "review_look_away.mp4"

RESOLUTION = [960, 540]
FPS        = 30
BG         = "#1a1a2e"


def escape(text: str) -> str:
    for c, r in [("\\", "\\\\"), ("'", "\\'"), (":", "\\:"), ("[", "\\["), ("]", "\\]")]:
        text = text.replace(c, r)
    return text


def render(manifest: dict, out: Path, label: str = "") -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    mf = TMP_DIR / f"{out.stem}_manifest.json"
    mf.write_text(json.dumps(dict(manifest, output=str(out)), indent=2))
    if label:
        print(f"  Rendering: {label} ...", flush=True)
    r = subprocess.run([str(RENDERER), "--scene", str(mf)],
                       capture_output=True, text=True, cwd=str(REPO_ROOT))
    if r.returncode != 0:
        print(f"  ERROR: {r.stdout[-1500:]}", file=sys.stderr)
        return False
    print(f"    → {out.name}  ({out.stat().st_size // 1024} KB)")
    return True


def annotate(raw: Path, ann: Path, line1: str, line2: str = "",
             fire_t: float = 0.0,
             motion_dur: float = 2.0,
             fade_dur: float = 1.0) -> bool:
    motion_end = fire_t + motion_dur
    fade_end   = motion_end + fade_dur

    parts = [
        # ── top bar ───────────────────────────────────────────────────────
        "drawbox=x=0:y=0:w=iw:h=80:color=black@0.85:t=fill",
        f"drawtext=text='{escape(line1)}'"
        ":fontsize=22:fontcolor=white"
        ":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ":x=(w-tw)/2:y=8:box=0",
    ]
    if line2:
        parts.append(
            f"drawtext=text='{escape(line2)}'"
            ":fontsize=14:fontcolor=#cccccc"
            ":x=(w-tw)/2:y=44:box=0"
        )

    # ── bottom-right timestamp ─────────────────────────────────────────────
    parts.append(
        "drawtext=text='t\\=%{eif\\:t\\:d}.%{eif\\:mod(t*100\\,100)\\:d}s'"
        ":fontsize=20:fontcolor=white"
        ":x=w-tw-12:y=h-36"
        ":box=1:boxcolor=black@0.7:boxborderw=4"
    )

    # ── bottom-left motion state panel ────────────────────────────────────
    # Background box (always visible)
    parts.append("drawbox=x=0:y=h-70:w=280:h=70:color=black@0.75:t=fill")

    # IDLE label — visible before fire and after fade completes
    parts.append(
        f"drawtext=text='motion\\: idle'"
        f":enable='lt(t,{fire_t})+gte(t,{fade_end})'"
        ":fontsize=17:fontcolor=#88ff88"
        ":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ":x=12:y=h-62:box=0"
    )

    # look_away label with remaining time — visible during motion
    parts.append(
        f"drawtext=text='motion\\: look_away'"
        f":enable='between(t,{fire_t},{motion_end})'"
        ":fontsize=17:fontcolor=#ffdd44"
        ":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ":x=12:y=h-62:box=0"
    )
    parts.append(
        f"drawtext=text='rem\\: %{{eif\\:{motion_end}-t\\:d}}.%{{eif\\:mod(({motion_end}-t)*10\\,10)\\:d}}s'"
        f":enable='between(t,{fire_t},{motion_end})'"
        ":fontsize=14:fontcolor=#ffdd44"
        ":x=12:y=h-38:box=0"
    )

    # fade_to_idle label with remaining time — visible during fade
    parts.append(
        f"drawtext=text='motion\\: fade_to_idle'"
        f":enable='between(t,{motion_end},{fade_end})'"
        ":fontsize=17:fontcolor=#44bbff"
        ":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ":x=12:y=h-62:box=0"
    )
    parts.append(
        f"drawtext=text='rem\\: %{{eif\\:{fade_end}-t\\:d}}.%{{eif\\:mod(({fade_end}-t)*10\\,10)\\:d}}s'"
        f":enable='between(t,{motion_end},{fade_end})'"
        ":fontsize=14:fontcolor=#44bbff"
        ":x=12:y=h-38:box=0"
    )

    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw),
         "-vf", ",".join(parts),
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-an",
         str(ann)],
        capture_output=True,
    )
    if r.returncode != 0:
        print(f"  ERROR annotate: {r.stderr.decode(errors='replace')[-800:]}", file=sys.stderr)
        return False
    return True


def make_title_card(text: str, out: Path, duration: float = 2.0) -> bool:
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c=black:size={RESOLUTION[0]}x{RESOLUTION[1]}:rate={FPS}:duration={duration}",
         "-vf",
         f"drawtext=text='{escape(text)}'"
         ":fontsize=32:fontcolor=white"
         ":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
         ":x=(w-tw)/2:y=(h-th)/2",
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         str(out)],
        capture_output=True,
    )
    return r.returncode == 0


def concat(clips: list[Path], out: Path) -> bool:
    lst = TMP_DIR / "concat.txt"
    lst.write_text("".join(f"file '{c}'\n" for c in clips))
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(out)],
        capture_output=True,
    )
    if r.returncode != 0:
        print(f"ERROR concat: {r.stderr.decode(errors='replace')[-800:]}", file=sys.stderr)
        return False
    return True


def base_manifest(cues: list) -> dict:
    return {
        "schema_version": "1.0",
        "model": {"id": "majo"},
        "audio": "",
        "output": "",
        "resolution": RESOLUTION,
        "fps": FPS,
        "background": BG,
        "lipsync": [],
        "cues": cues,
    }


def main():
    if not RENDERER.exists():
        print(f"ERROR: renderer not found at {RENDERER}", file=sys.stderr)
        sys.exit(1)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # look_away duration=2.0s, fade_to_idle=1.0s → motion fully done by ~t=5s after fire.
    # Sentinel at fire_t + 7.0 gives 5s idle buffer after motion exits.
    clips: list[Path] = []

    variants = [
        (2.0,  "Clip A — fire at t=2.0 (breath near neutral, best case)",
               "Idle 2s → look_away → watch exit snap into idle"),
        (3.27, "Clip B — fire at t=3.27 (AngleX near negative peak, worst case)",
               "Idle 3.27s → look_away → exit snap at breath peak"),
        (0.5,  "Clip C — fire at t=0.5  (mid-rise, intermediate)",
               "Idle 0.5s → look_away → exit snap mid-breath-rise"),
    ]

    title = TMP_DIR / "title.mp4"
    make_title_card("look_away — exit snap review", title, duration=2.5)
    clips.append(title)

    for fire_t, line1, line2 in variants:
        sentinel_t = fire_t + 7.0
        cues = [
            {"time": 0.0,        "emotion": "neutral"},
            {"time": fire_t,     "reaction": "look_away"},
            {"time": sentinel_t, "emotion": "neutral"},
        ]
        raw = TMP_DIR / f"clip_fire{fire_t:.2f}_raw.mp4"
        ann = TMP_DIR / f"clip_fire{fire_t:.2f}_ann.mp4"

        if not render(base_manifest(cues), raw, label=line1):
            sys.exit(1)
        if not annotate(raw, ann, line1, line2, fire_t=fire_t,
                        motion_dur=2.0, fade_dur=1.0):
            sys.exit(1)
        clips.append(ann)

    print(f"\nConcatenating {len(clips)} clips → {FINAL} ...")
    if not concat(clips, FINAL):
        sys.exit(1)

    size_mb = FINAL.stat().st_size / (1024 * 1024)
    print(f"\nDONE  →  {FINAL}  ({size_mb:.1f} MB)")
    print("""
Review checklist:
  Clip A (best case):   does idle resume cleanly, or is there a snap at the exit?
  Clip B (worst case):  snap most visible here — head jumps as breath resumes at peak
  Clip C (mid-rise):    intermediate — helps isolate whether snap scales with breath phase
""")


if __name__ == "__main__":
    main()
