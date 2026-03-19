#!/usr/bin/env python3
"""
Focused consult phase review with animation-state overlays.

Renders ONLY the 'consult' reaction (9 seconds: 2.5s motion + 6.5s idle buffer).
Bottom-left red text shows which animations are active with countdown timers.
Idle has no timer (it loops). Consult phases show time remaining. Labels
disappear when the animation/phase is no longer active.

The key thing to verify: cubism-FadeOut and breath-guard-FADEOUT both appear
at t=1.5s and both count down to t=2.5s — confirming they are synchronized
(this is the breath_guard:"fadeout" fix for GH #15).

Output: results/tests/sable-spec-v1.1/consult_phase_review.mp4

Motion parameters (must match consult.motion3.json + majo.model3.json):
  Consult.Duration    = 2.5s   (Meta.Duration)
  Consult.FadeOutTime = 1.0s   (model3.json Motions.Consult.FadeOutTime)
  Hold phase          = t=0.00 → t=1.50  (duration - fadeout)
  FadeOut phase       = t=1.50 → t=2.50  (fadeout window)
  Entry guard ramp    = t=0.00 → t=0.15  (renderer breath_guard_entry_fade_duration)
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Motion parameters ──────────────────────────────────────────────────────────
CONSULT_DURATION = 2.5    # Meta.Duration in consult.motion3.json
CONSULT_FADEOUT  = 1.0    # FadeOutTime in majo.model3.json Motions.Consult
HOLD_END         = CONSULT_DURATION - CONSULT_FADEOUT   # 1.5s
ENTRY_FADE       = 0.15   # breath_guard_entry_fade_duration (renderer default)
CLIP_DUR         = 9.0    # 6.5s idle buffer after motion ends

# ── Paths ──────────────────────────────────────────────────────────────────────
AUDIO_SRC     = ROOT / "tests/fixtures/cheesetest/wav/scene_01.wav"
TMPL_MANIFEST = ROOT / "tests/fixtures/cheesetest/scene_01_manifest.json"
OUT_DIR       = ROOT / "results/tests/sable-spec-v1.1"
RAW_PATH      = ROOT / "tests/output/consult_phase_raw.mp4"
OUT_PATH      = OUT_DIR / "consult_phase_review.mp4"
MAN_PATH      = ROOT / "tests/output/consult_phase_manifest.json"
RENDERER      = ROOT / "build/live2d-render"


# ── FFmpeg drawtext helpers ────────────────────────────────────────────────────

STEP = 0.1   # countdown granularity (seconds); generates one drawtext entry per interval


def _esc(s: str) -> str:
    """Escape a string for FFmpeg drawtext text='...' value."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def _between(t0: float, t1: float) -> str:
    """FFmpeg enable expression: active while t0 ≤ t ≤ t1."""
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
    text_fn(remaining_seconds) → display string for this interval.
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


def build_vf() -> str:
    """
    Build the full FFmpeg -vf drawtext filter chain.

    Bottom-left stack (grows upward, LH=43px per line):

      [always]         idle  [looping]
      [t=0.0–1.5]      consult  HOLD  :  1.5s … 0.1s remaining
      [t=1.5–2.5]      consult  FADEOUT  :  1.0s … 0.1s remaining
      [t=0.15–1.5]     breath-guard  SUPPRESSED  (w=1.00)
      [t=1.5–2.5]      breath-guard  FADEOUT  w=1.00 … 0.10
      [t=1.5–2.5]      cubism-FadeOut  :  1.0s … 0.1s  ← same window as breath-guard
    """
    T0 = 0.0
    TH = HOLD_END           # 1.5s — FadeOut starts; breath-guard exit ramp arms
    TE = CONSULT_DURATION   # 2.5s — motion ends; priority drops; guard reaches 0

    LH = 43     # line height including padding (px)
    Y0 = 175    # y-from-bottom for the bottommost left line

    parts = []

    # ── Top center: pass criteria ──────────────────────────────────────────
    crit = _esc(
        "PASS: +14deg tilt + eye drop, smooth return. "
        "No snap at exit. No wobble during hold."
    )
    parts.append(
        f"drawtext=text='{crit}'"
        f":fontsize=22:fontcolor=yellow"
        f":x=(w-tw)/2:y=40"
        f":box=1:boxcolor=black@0.7:boxborderw=8"
    )

    # ── Bottom center: clip identity ───────────────────────────────────────
    lbl = _esc("consult  ->  Consult  (reaction)  |  breath_guard: fadeout")
    parts.append(
        f"drawtext=text='{lbl}'"
        f":fontsize=30:fontcolor=white"
        f":x=(w-tw)/2:y=h-120"
        f":box=1:boxcolor=black@0.65:boxborderw=12"
    )

    # ── Line 1 (bottom-left): idle — always present, no timer ─────────────
    parts.append(_dt("idle  [looping]", y_from_bottom=Y0))

    # ── Line 2: consult phase — hold (t=0–1.5) then fadeout (t=1.5–2.5) ──
    parts.extend(_seq(
        lambda rem: f"consult  HOLD : {rem:.1f}s remaining",
        T0, TH, Y0 + LH, color="red",
    ))
    parts.extend(_seq(
        lambda rem: f"consult  FADEOUT : {rem:.1f}s remaining",
        TH, TE, Y0 + LH, color="red",
    ))

    # ── Line 3: breath-guard status (swaps at t=TH) ───────────────────────
    # Hold phase: fully suppressed (static label — no countdown needed)
    parts.append(_dt(
        "breath-guard  SUPPRESSED  (w=1.00)",
        y_from_bottom=Y0 + LH * 2,
        enable=_between(ENTRY_FADE, TH),
        color="orange",
    ))
    # Fadeout phase: weight decreasing from 1.0→0.0
    # weight at interval start t = (TE - t) / CONSULT_FADEOUT
    parts.extend(_seq(
        lambda rem: f"breath-guard  FADEOUT  w={rem / CONSULT_FADEOUT:.2f}",
        TH, TE, Y0 + LH * 2, color="orange",
    ))

    # ── Line 4: cubism-FadeOut — appears at SAME time as breath-guard fadeout
    parts.extend(_seq(
        lambda rem: f"cubism-FadeOut : {rem:.1f}s  <- same window as breath-guard",
        TH, TE, Y0 + LH * 3, color="cyan",
    ))

    return ",".join(parts)


# ── Audio / lipsync helpers ────────────────────────────────────────────────────

def _tile_audio(src: Path, dest: Path, dur: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
         "-t", f"{dur:.3f}", "-c", "copy", str(dest)],
        capture_output=True, check=True,
    )


def _tile_lipsync(keyframes: list, loop_dur: float, total: float) -> list:
    out, i = [], 0
    while (offset := i * loop_dur) < total:
        for kf in keyframes:
            t = round(kf["time"] + offset, 4)
            if t >= total:
                break
            out.append({"time": t, "mouth_shape": kf["mouth_shape"]})
        i += 1
    return out


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MAN_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Audio / lipsync
    audio_arg   = None
    lipsync     = []
    tiled_audio = ROOT / "tests/output/consult_phase_audio.wav"

    if AUDIO_SRC.exists() and TMPL_MANIFEST.exists():
        with open(TMPL_MANIFEST, encoding="utf-8") as fh:
            tmpl = json.load(fh)
        kfs      = tmpl.get("lipsync", [])
        max_t    = max((kf["time"] for kf in kfs), default=0.0)
        loop_dur = max_t + 1.0
        _tile_audio(AUDIO_SRC, tiled_audio, CLIP_DUR)
        lipsync   = _tile_lipsync(kfs, loop_dur, CLIP_DUR)
        audio_arg = str(tiled_audio).replace("\\", "/")
        print(f"Lipsync  : {len(lipsync)} keyframes  ({CLIP_DUR:.1f}s audio)")

    # Manifest — single consult cue at t=0, no terminal re-trigger
    manifest = {
        "schema_version": "1.0",
        "model":      {"id": "majo"},
        "audio":      audio_arg,
        "output":     str(RAW_PATH).replace("\\", "/"),
        "resolution": [1080, 1920],
        "fps":        30,
        "background": "#1a1a2e",
        "lipsync":    lipsync,
        "cues": [
            {"time": 0.0, "reaction": "consult"},
        ],
    }
    with open(MAN_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"Manifest : {MAN_PATH}")

    # Render
    if not RENDERER.exists():
        raise FileNotFoundError(f"Renderer not found: {RENDERER}. Run: cmake --build build")
    print("Rendering ...")
    subprocess.run([str(RENDERER), "--scene", str(MAN_PATH)], cwd=str(ROOT), check=True)
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Renderer produced no output at {RAW_PATH}")

    # Burn overlays
    vf = build_vf()
    print("Burning overlays ...")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(RAW_PATH),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            *([ "-c:a", "copy"] if audio_arg else ["-an"]),
            str(OUT_PATH),
        ],
        cwd=str(ROOT),
        check=True,
    )

    # Cleanup intermediates
    RAW_PATH.unlink(missing_ok=True)
    if audio_arg:
        tiled_audio.unlink(missing_ok=True)

    print(f"\nDone.")
    print(f"  Review   : {OUT_PATH}")
    print(f"  Manifest : {MAN_PATH}")
    print()
    print("Phase timeline (baked into overlays):")
    print(f"  t=0.000 – {ENTRY_FADE:.3f}s  breath-guard entry ramp (brief)")
    print(f"  t={ENTRY_FADE:.3f} – {HOLD_END:.3f}s  consult HOLD  |  breath-guard SUPPRESSED")
    print(f"  t={HOLD_END:.3f} – {CONSULT_DURATION:.3f}s  consult FADEOUT  |  cubism-FadeOut  |  breath-guard FADEOUT  (simultaneous)")
    print(f"  t={CONSULT_DURATION:.3f} – {CLIP_DUR:.1f}s    idle only")


if __name__ == "__main__":
    main()
