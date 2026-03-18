#!/usr/bin/env python3
"""
Round 2 — Re-render 5 clips with structural improvements:
  - 3s idle baseline before reactions (was 1s)
  - 5s padding at end of every clip
  - Standalone idle clip as first reaction clip

Clips:
  1. EXPRESSION: embarrassed (with Param21 cheek puff blush proxy)
  2. REACTION:   idle (5s standalone baseline)
  3. REACTION:   nod  (3s baseline + trigger at t=3.0s + 5s tail)
  4. REACTION:   look_away (3s baseline + trigger at t=3.0s + 5s tail)
  5. REACTION:   tap  (3s baseline + trigger at t=3.0s + 5s tail)
"""

import json
import subprocess
import sys
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
ROOT     = Path("/workspaces/hub_1/live2d")
RENDERER = Path("/tmp/live2d_build/live2d-render")
OUT_DIR  = ROOT / "tests/fixtures/majo_review"
TMP_DIR  = OUT_DIR / "_tmp_round2"
FINAL    = OUT_DIR / "round_2_revised.mp4"

TOTAL_CLIPS = 5
HEADER_LINE1 = "MAJO BEHAVIOUR REVIEW — ROUND 2"

# ── clip definitions ───────────────────────────────────────────────────────────
# duration: renderer uses last cue time + ~1s; we use a terminal hold cue to
# pin the exact end point.
#
# Timing notes:
#   embarrassed  : 4s total   neutral 0.5s → embarrassed 0.5s → hold 3.0s → 4s
#   idle         : 5s total   idle 0s → hold 4.0s → 5s
#   nod          : 9s total   idle 0s, nod 3.0s (0.5s), idle-hold 8.0s → 9s
#   look_away    : 9.5s total idle 0s, look_away 3.0s (1.5s), idle-hold 8.5s → 9.5s
#   tap          : 9s total   idle 0s, tap 3.0s (1.0s), idle-hold 8.0s → 9s

CLIPS = [
    # ── 1. Expression: embarrassed ────────────────────────────────────────────
    {
        "index":  1,
        "stem":   "round_2_embarrassed",
        "label2": "EXPRESSION: embarrassed — raised brows, slight smile, cheek puff (blush proxy). Compare to angry — should look flustered not angry.",
        "duration": 4.0,
        "cues": [
            {"time": 0.0, "emotion": "neutral"},
            {"time": 0.5, "emotion": "embarrassed"},
            {"time": 3.0, "emotion": "embarrassed"},   # terminal hold → 4s
        ],
    },

    # ── 2. Reaction: idle (standalone 5s baseline) ────────────────────────────
    {
        "index":  2,
        "stem":   "round_2_idle",
        "label2": "REACTION: idle — 5s of normal idle. The head oscillation shown here (CubismBreath) is the baseline state before any reaction.",
        "duration": 5.0,
        "cues": [
            {"time": 0.0, "reaction": "idle"},
            {"time": 4.0, "reaction": "idle"},   # terminal hold → 5s
        ],
    },

    # ── 3. Reaction: nod ──────────────────────────────────────────────────────
    {
        "index":  3,
        "stem":   "round_2_nod",
        "label2": "REACTION: nod — reaction fires at t=3.0s. Watch for head dipping forward. Idle baseline shown first for 3s.",
        "duration": 9.0,
        "cues": [
            {"time": 0.0, "reaction": "idle"},
            {"time": 3.0, "reaction": "nod"},
            {"time": 8.0, "reaction": "idle"},   # terminal hold → 9s
        ],
    },

    # ── 4. Reaction: look_away ────────────────────────────────────────────────
    {
        "index":  4,
        "stem":   "round_2_look_away",
        "label2": "REACTION: look_away — reaction fires at t=3.0s. Watch for eyes+head turning right. Idle baseline shown first for 3s.",
        "duration": 9.5,
        "cues": [
            {"time": 0.0, "reaction": "idle"},
            {"time": 3.0, "reaction": "look_away"},
            {"time": 8.5, "reaction": "idle"},   # terminal hold → 9.5s
        ],
    },

    # ── 5. Reaction: tap ──────────────────────────────────────────────────────
    {
        "index":  5,
        "stem":   "round_2_tap",
        "label2": "REACTION: tap — reaction fires at t=3.0s. Watch for head jolting sideways. Idle baseline shown first for 3s.",
        "duration": 9.0,
        "cues": [
            {"time": 0.0, "reaction": "idle"},
            {"time": 3.0, "reaction": "tap"},
            {"time": 8.0, "reaction": "idle"},   # terminal hold → 9s
        ],
    },
]


def escape_drawtext(text: str) -> str:
    """Escape text for FFmpeg drawtext filter."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'",  "\\'")
    text = text.replace(":",  "\\:")
    text = text.replace("[",  "\\[")
    text = text.replace("]",  "\\]")
    return text


def render_raw(clip: dict, raw_path: Path) -> tuple[bool, str]:
    """Write manifest and invoke renderer. Returns (success, log_text)."""
    manifest = {
        "schema_version": "1.0",
        "model": {"id": "majo"},
        "audio": None,
        "output": str(raw_path.relative_to(ROOT)),
        "resolution": [1280, 720],
        "fps": 30,
        "background": "#1a1a2e",
        "lipsync": [],
        "cues": clip["cues"],
    }

    manifest_path = TMP_DIR / f"clip_{clip['index']:02d}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"  Rendering [{clip['index']}/{TOTAL_CLIPS}] {clip['stem']} ({clip['duration']}s) ...")
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


def annotate_clip(clip: dict, raw_path: Path, out_path: Path) -> bool:
    """Burn header, timestamp, and clip-index annotations onto the raw clip."""
    h1_esc  = escape_drawtext(HEADER_LINE1)
    h2_esc  = escape_drawtext(clip["label2"])
    idx_str = escape_drawtext(f"[{clip['index']}/{TOTAL_CLIPS}]")

    vf_parts = [
        # Black header bar ~110px
        "drawbox=x=0:y=0:w=iw:h=110:color=black@0.7:t=fill",

        # Line 1: main header, bold white ~28pt, y=12
        f"drawtext=text='{h1_esc}'"
        f":fontsize=28:fontcolor=white:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f":x=(w-tw)/2:y=12:box=0",

        # Line 2: clip description, white ~18pt, y=52
        f"drawtext=text='{h2_esc}'"
        f":fontsize=18:fontcolor=white"
        f":x=(w-tw)/2:y=52:box=0",

        # Timestamp bottom-right: t=X.XXs
        "drawtext=text='t\\=%{eif\\:t\\:d}.%{eif\\:mod(t*100\\,100)\\:d}s'"
        ":fontsize=28:fontcolor=white"
        ":x=w-tw-20:y=h-50"
        ":box=1:boxcolor=black@0.7:boxborderw=8",

        # Clip index bottom-left
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


def get_size_kb(path: Path) -> int:
    return path.stat().st_size // 1024


def extract_reaction_log_lines(log: str, reaction: str) -> list[str]:
    """Pull out relevant renderer log lines for a reaction cue."""
    keywords = [
        f'reaction → "{reaction}"',
        f'reaction "{reaction}"',
        "TriggerMotion",
        "Cue t=",
        "not found",
        "skipped",
        "not in model",
    ]
    lines = []
    for line in log.splitlines():
        if any(kw in line for kw in keywords):
            lines.append(line)
    return lines


def main():
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rendered = []   # (clip, annotated_path, duration, log)
    failed   = []

    for clip in CLIPS:
        raw_path = TMP_DIR / f"clip_{clip['index']:02d}_raw.mp4"
        ann_path = OUT_DIR / f"{clip['stem']}.mp4"

        ok, log = render_raw(clip, raw_path)
        if not ok:
            failed.append((clip["stem"], "render failed"))
            continue

        ok = annotate_clip(clip, raw_path, ann_path)
        if not ok:
            failed.append((clip["stem"], "annotation failed"))
            continue

        dur = get_duration(ann_path)
        rendered.append((clip, ann_path, dur, log))
        print(f"  OK: {clip['stem']} — {dur:.2f}s")

        # Log reaction-specific lines for reaction clips
        if any("reaction" in c for c in clip["cues"]):
            reaction_name = next(
                (c["reaction"] for c in clip["cues"] if "reaction" in c and c["reaction"] != "idle"),
                None,
            )
            if reaction_name:
                lines = extract_reaction_log_lines(log, reaction_name)
                if lines:
                    print(f"    Reaction log lines for '{reaction_name}':")
                    for ln in lines:
                        print(f"      {ln}")
                else:
                    print(f"    [no reaction-specific log lines found for '{reaction_name}']")
                    print(f"    Full log excerpt (first 30 lines):")
                    for ln in log.splitlines()[:30]:
                        print(f"      {ln}")

    if not rendered:
        print("ERROR: No clips rendered successfully.", file=sys.stderr)
        sys.exit(1)

    # ── concatenate all annotated clips ────────────────────────────────────────
    concat_list = TMP_DIR / "concat_round2.txt"
    with open(concat_list, "w") as fh:
        for _, ap, _, _ in rendered:
            fh.write(f"file '{ap}'\n")

    print(f"\nConcatenating {len(rendered)} clips into round_2_revised.mp4 ...")
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

    # ── report ─────────────────────────────────────────────────────────────────
    total_dur = sum(d for _, _, d, _ in rendered)
    final_size = get_size_kb(FINAL)

    print(f"\n{'='*70}")
    print("DONE — round_2_revised.mp4")
    print(f"  Output : {FINAL}")
    print(f"  Size   : {final_size} KB")
    print(f"  Total  : {total_dur:.2f}s  ({len(rendered)}/{TOTAL_CLIPS} clips)")
    print()
    print("Per-clip summary:")
    for clip, ap, dur, log in rendered:
        size_kb = get_size_kb(ap)
        print(f"  [{clip['index']}/{TOTAL_CLIPS}] {clip['stem']}  duration={dur:.2f}s  size={size_kb}KB")

        # Show reaction trigger lines for reaction clips
        if any("reaction" in c for c in clip["cues"]):
            reaction_name = next(
                (c["reaction"] for c in clip["cues"] if "reaction" in c and c["reaction"] != "idle"),
                None,
            )
            if reaction_name:
                lines = extract_reaction_log_lines(log, reaction_name)
                if lines:
                    for ln in lines:
                        print(f"       LOG: {ln}")
                else:
                    print(f"       LOG: [no trigger lines found for '{reaction_name}']")

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for stem, reason in failed:
            print(f"  {stem}: {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
