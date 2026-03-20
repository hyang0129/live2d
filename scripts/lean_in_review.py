#!/usr/bin/env python3
"""
Focused lean_in debug review — motion-to-fade_to_idle transition inspection.

Renders ONLY the 'lean_in' reaction (12 seconds: 3.2s motion + 1.0s fade_to_idle + 7.8s idle).
Bottom-left text shows animation phase with countdown timers.
Renderer runs at --log-level debug so [fade_to_idle] per-frame values are captured.

Phase timeline:
  t=0.000 – 3.200s  lean_in playing   (FadeOutTime=0, curve returns to 0)
  t=3.200 – 4.200s  fade-to-idle      (1.0s blend: snapshot → idle+breath)
  t=4.200 – 12.0s   idle only         (transition complete)

The snap (if any) occurs at t≈3.200 — inspect AngleY values in debug log
around the arm event and the first few lerp frames.

Output:
  results/tests/sable-spec-v1.1/lean_in_debug_review.mp4
  tests/output/lean_in_debug_raw.log   ← debug log with per-frame fade values
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Motion parameters (must match lean_in.motion3.json + registry.json) ───────
LEAN_IN_DURATION  = 3.2    # Meta.Duration (FadeOutTime = 0 on curve)
FADE_TO_IDLE_DUR  = 1.0    # fade_to_idle_duration from registry
FADE_TO_IDLE_END  = LEAN_IN_DURATION + FADE_TO_IDLE_DUR   # 4.2s
CLIP_DUR          = 12.0   # 7.8s idle buffer after fade-to-idle ends

# ── Paths ──────────────────────────────────────────────────────────────────────
AUDIO_SRC     = ROOT / "tests/fixtures/cheesetest/wav/scene_01.wav"
TMPL_MANIFEST = ROOT / "tests/fixtures/cheesetest/scene_01_manifest.json"
OUT_DIR       = ROOT / "results/tests/sable-spec-v1.1"
RAW_PATH      = ROOT / "tests/output/lean_in_debug_raw.mp4"
LOG_PATH      = ROOT / "tests/output/lean_in_debug_raw.log"
OUT_PATH      = OUT_DIR / "lean_in_debug_review.mp4"
MAN_PATH      = ROOT / "tests/output/lean_in_debug_manifest.json"
VF_PATH       = ROOT / "tests/output/lean_in_debug_vf.txt"
RENDERER      = ROOT / "build/live2d-render"


# ── FFmpeg drawtext helpers ────────────────────────────────────────────────────

STEP = 0.1


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def _between(t0: float, t1: float) -> str:
    return f"between(t\\,{t0:.3f}\\,{t1:.3f})"


def _dt(text: str, y_from_bottom: int, enable: str = "1",
        color: str = "red", fontsize: int = 21) -> str:
    return (
        f"drawtext=text='{text}'"
        f":enable='{enable}'"
        f":fontsize={fontsize}:fontcolor={color}"
        f":x=18:y=h-{y_from_bottom}"
        f":box=1:boxcolor=black@0.78:boxborderw=6"
    )


def _seq(text_fn, phase_start: float, phase_end: float,
         y_from_bottom: int, color: str = "red") -> list:
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
    Build FFmpeg drawtext filter chain.

    Bottom-left stack (LH=43px per line):
      [always]              idle  [looping]
      [t=0.0–3.2]           lean_in (playing) : Xs remaining
      [t=3.2–4.2]           fade-to-idle : 1.0s … 0.1s remaining
    """
    TE  = LEAN_IN_DURATION   # 3.2s — motion ends
    TFI = FADE_TO_IDLE_END   # 4.2s — fade-to-idle complete

    LH = 43
    Y0 = 175

    parts = []

    # Top centre: pass criteria
    crit = _esc(
        "PASS: very slow 1.2s onset, −10° hold, smooth 1.0s return. "
        "INSPECT: AngleY snap at t=3.2 (motion→fade_to_idle). See debug log."
    )
    parts.append(
        f"drawtext=text='{crit}'"
        f":fontsize=22:fontcolor=yellow"
        f":x=(w-tw)/2:y=40"
        f":box=1:boxcolor=black@0.7:boxborderw=8"
    )

    # Bottom centre: clip identity
    lbl = _esc(
        "lean_in  →  LeanIn  (reaction)  |  FadeOutTime=0  |  "
        "fade_to_idle: 1.0s  |  breath_guard: none"
    )
    parts.append(
        f"drawtext=text='{lbl}'"
        f":fontsize=28:fontcolor=white"
        f":x=(w-tw)/2:y=h-120"
        f":box=1:boxcolor=black@0.65:boxborderw=12"
    )

    # Transition marker — vertical-line-like text at t=3.2
    parts.append(
        f"drawtext=text='▼ TRANSITION t\\=3.2s'"
        f":enable='{_between(3.1, 3.35)}'"
        f":fontsize=28:fontcolor=orange"
        f":x=(w-tw)/2:y=h/2-60"
        f":box=1:boxcolor=black@0.75:boxborderw=10"
    )

    # Line 1: idle (always)
    parts.append(_dt("idle  [looping]", y_from_bottom=Y0))

    # Line 2: lean_in playing
    parts.extend(_seq(
        lambda rem: f"lean_in (playing) : {rem:.1f}s remaining",
        0.0, TE, Y0 + LH, color="red",
    ))

    # Line 3: fade-to-idle window
    parts.extend(_seq(
        lambda rem: f"fade-to-idle : {rem:.1f}s remaining",
        TE, TFI, Y0 + LH * 2, color="cyan",
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
    tiled_audio = ROOT / "tests/output/lean_in_debug_audio.wav"

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

    # Manifest — single lean_in cue at t=0
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
            {"time": 0.0, "reaction": "lean_in"},
        ],
    }
    with open(MAN_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"Manifest : {MAN_PATH}")

    # Render with debug logging
    if not RENDERER.exists():
        raise FileNotFoundError(f"Renderer not found: {RENDERER}")
    print("Rendering (--log-level debug) ...")
    subprocess.run(
        [str(RENDERER), "--scene", str(MAN_PATH), "--log-level", "debug"],
        cwd=str(ROOT), check=True,
    )
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Renderer produced no output at {RAW_PATH}")
    print(f"Debug log: {LOG_PATH}")

    # Extract the transition-window log lines for quick inspection
    print("\n── fade_to_idle transition (from debug log) ──────────────────────────")
    if LOG_PATH.exists():
        lines = LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines:
            if "[fade_to_idle]" in line:
                print(line)
    print("─────────────────────────────────────────────────────────────────────\n")

    # Burn overlays — write VF to file to avoid ARG_MAX
    vf = build_vf()
    VF_PATH.write_text(vf, encoding="utf-8")

    print("Burning overlays ...")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(RAW_PATH),
            "-filter_script:v", str(VF_PATH),
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            *([ "-c:a", "copy"] if audio_arg else ["-an"]),
            str(OUT_PATH),
        ],
        cwd=str(ROOT),
        check=True,
    )

    # Cleanup intermediates
    RAW_PATH.unlink(missing_ok=True)
    VF_PATH.unlink(missing_ok=True)
    if audio_arg:
        tiled_audio.unlink(missing_ok=True)

    print(f"\nDone.")
    print(f"  Review   : {OUT_PATH}")
    print(f"  Debug log: {LOG_PATH}")
    print()
    print("Phase timeline:")
    print(f"  t=0.000  – {LEAN_IN_DURATION:.3f}s  lean_in playing  (FadeOutTime=0)")
    print(f"  t={LEAN_IN_DURATION:.3f}  – {FADE_TO_IDLE_END:.3f}s  fade-to-idle  ({FADE_TO_IDLE_DUR:.1f}s)")
    print(f"  t={FADE_TO_IDLE_END:.3f}  – {CLIP_DUR:.1f}s   idle only")


if __name__ == "__main__":
    main()
