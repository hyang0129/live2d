#!/usr/bin/env python3
"""
Consult fade-to-idle comparison: global (1.0s) vs explicit (0.7s).

Clip A — Global fade-to-idle:
  Temporarily removes fade_to_idle_duration from the consult registry entry
  so the renderer falls back to renderer_config.json → animation.fade_to_idle_duration = 1.0s

Clip B — Explicit fade-to-idle:
  Current consult entry with fade_to_idle_duration = 0.7s

Both clips are rendered at full resolution, then scaled and stitched
side by side (hstack) for direct comparison.

Output: results/tests/sable-spec-v1.1/consult_compare.mp4
"""
import json
import subprocess
import shutil
from pathlib import Path

ROOT      = Path(__file__).resolve().parent.parent
REGISTRY  = ROOT / "assets/models/registry.json"
RENDERER  = ROOT / "build/live2d-render"
AUDIO_SRC = ROOT / "tests/fixtures/cheesetest/wav/scene_01.wav"
TMPL_MAN  = ROOT / "tests/fixtures/cheesetest/scene_01_manifest.json"
TMP_DIR   = ROOT / "tests/output"
OUT_DIR   = ROOT / "results/tests/sable-spec-v1.1"

CONSULT_DURATION = 2.5   # Meta.Duration in consult.motion3.json
CLIP_DUR         = 9.0   # 5+ s idle buffer after fade-to-idle ends
STEP             = 0.1   # countdown granularity (s)

GLOBAL_FADE_DUR  = 1.0   # renderer_config.json → animation.fade_to_idle_duration
EXPLICIT_FADE_DUR = 0.7  # current per-motion override in registry


# ── FFmpeg drawtext helpers ────────────────────────────────────────────────────

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


def build_vf(fade_dur: float, label: str, crit: str) -> str:
    """
    Overlay filter for one clip.
    Bottom-left stack:
      Line 1 (always):       idle  [looping]
      Line 2 (t=0–2.5):      consult (playing) : Xs remaining
      Line 3 (t=2.5–fade_end): fade-to-idle : Xs remaining  (cyan)
    Top center: pass criteria (yellow)
    Bottom center: clip identity label (white)
    """
    TE  = CONSULT_DURATION
    TFI = round(CONSULT_DURATION + fade_dur, 3)
    LH  = 43
    Y0  = 175

    parts = []

    # Top center: criteria
    parts.append(
        f"drawtext=text='{_esc(crit)}'"
        f":fontsize=22:fontcolor=yellow"
        f":x=(w-tw)/2:y=40"
        f":box=1:boxcolor=black@0.7:boxborderw=8"
    )

    # Bottom center: clip label
    parts.append(
        f"drawtext=text='{_esc(label)}'"
        f":fontsize=28:fontcolor=white"
        f":x=(w-tw)/2:y=h-120"
        f":box=1:boxcolor=black@0.65:boxborderw=12"
    )

    # Line 1: idle [looping]
    parts.append(_dt("idle  [looping]", y_from_bottom=Y0))

    # Line 2: consult playing
    parts.extend(_seq(
        lambda rem: f"consult (playing) : {rem:.1f}s remaining",
        0.0, TE, Y0 + LH, color="red",
    ))

    # Line 3: fade-to-idle
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


# ── Registry patch helpers ─────────────────────────────────────────────────────

def _read_registry() -> list:
    with open(REGISTRY, encoding="utf-8") as fh:
        return json.load(fh)


def _write_registry(data: list) -> None:
    with open(REGISTRY, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def _patch_consult(remove_duration_override: bool) -> dict:
    """
    Modifies the majo consult reaction in-place.
    If remove_duration_override=True, removes fade_to_idle_duration so
    the renderer uses the global default from renderer_config.json.
    Returns the original consult entry for restoration.
    """
    registry = _read_registry()
    majo = next(m for m in registry if m["id"] == "majo")
    original = dict(majo["reactions"]["consult"])
    if remove_duration_override:
        majo["reactions"]["consult"].pop("fade_to_idle_duration", None)
    _write_registry(registry)
    return original


def _restore_consult(original: dict) -> None:
    registry = _read_registry()
    majo = next(m for m in registry if m["id"] == "majo")
    majo["reactions"]["consult"] = original
    _write_registry(registry)


# ── Render one clip ────────────────────────────────────────────────────────────

def render_clip(raw_path: Path, man_path: Path, audio_path: Path,
                lipsync: list, audio_arg: str | None) -> None:
    manifest = {
        "schema_version": "1.0",
        "model":      {"id": "majo"},
        "audio":      audio_arg,
        "output":     str(raw_path).replace("\\", "/"),
        "resolution": [1080, 1920],
        "fps":        30,
        "background": "#1a1a2e",
        "lipsync":    lipsync,
        "cues":       [{"time": 0.0, "reaction": "consult"}],
    }
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    subprocess.run([str(RENDERER), "--scene", str(man_path)], cwd=str(ROOT), check=True)
    if not raw_path.exists():
        raise FileNotFoundError(f"Renderer produced no output at {raw_path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not RENDERER.exists():
        raise FileNotFoundError(f"Renderer not found: {RENDERER}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Audio / lipsync
    audio_arg = None
    lipsync   = []
    tiled_audio = TMP_DIR / "consult_compare_audio.wav"

    if AUDIO_SRC.exists() and TMPL_MAN.exists():
        with open(TMPL_MAN, encoding="utf-8") as fh:
            tmpl = json.load(fh)
        kfs      = tmpl.get("lipsync", [])
        max_t    = max((kf["time"] for kf in kfs), default=0.0)
        loop_dur = max_t + 1.0
        _tile_audio(AUDIO_SRC, tiled_audio, CLIP_DUR)
        lipsync   = _tile_lipsync(kfs, loop_dur, CLIP_DUR)
        audio_arg = str(tiled_audio).replace("\\", "/")
        print(f"Lipsync  : {len(lipsync)} keyframes  ({CLIP_DUR:.1f}s audio)")

    # ── Clip A: global fade-to-idle (1.0s) ────────────────────────────────────
    print("\n=== Clip A: global fade-to-idle (1.0s) ===")
    raw_a = TMP_DIR / "consult_compare_a_raw.mp4"
    ann_a = TMP_DIR / "consult_compare_a.mp4"
    man_a = TMP_DIR / "consult_compare_a_manifest.json"

    original_consult = _patch_consult(remove_duration_override=True)
    try:
        render_clip(raw_a, man_a, tiled_audio, lipsync, audio_arg)
    finally:
        _restore_consult(original_consult)

    vf_a = build_vf(
        fade_dur=GLOBAL_FADE_DUR,
        label="[A]  global fade-to-idle  (1.0s)  —  no per-motion override",
        crit="PASS: smooth exit with no snap. Compare fade-to-idle window vs [B].",
    )
    print("Burning overlays [A] ...")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw_a), "-vf", vf_a,
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         *([ "-c:a", "copy"] if audio_arg else ["-an"]), str(ann_a)],
        cwd=str(ROOT), check=True,
    )
    raw_a.unlink(missing_ok=True)

    # ── Clip B: explicit fade-to-idle (0.7s) ──────────────────────────────────
    print("\n=== Clip B: explicit fade-to-idle (0.7s) ===")
    raw_b = TMP_DIR / "consult_compare_b_raw.mp4"
    ann_b = TMP_DIR / "consult_compare_b.mp4"
    man_b = TMP_DIR / "consult_compare_b_manifest.json"

    render_clip(raw_b, man_b, tiled_audio, lipsync, audio_arg)

    vf_b = build_vf(
        fade_dur=EXPLICIT_FADE_DUR,
        label="[B]  explicit fade-to-idle  (0.7s)  —  per-motion override",
        crit="PASS: smooth exit with no snap. Compare fade-to-idle window vs [A].",
    )
    print("Burning overlays [B] ...")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw_b), "-vf", vf_b,
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         *([ "-c:a", "copy"] if audio_arg else ["-an"]), str(ann_b)],
        cwd=str(ROOT), check=True,
    )
    raw_b.unlink(missing_ok=True)

    # ── Stitch side by side ───────────────────────────────────────────────────
    out_path = OUT_DIR / "consult_compare.mp4"
    print("\nStitching side by side ...")
    # Scale each 1080x1920 → 540x960, then hstack → 1080x960
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(ann_a),
            "-i", str(ann_b),
            "-filter_complex",
            "[0:v]scale=540:960[va];[1:v]scale=540:960[vb];[va][vb]hstack=inputs=2[v]",
            "-map", "[v]",
            *([ "-map", "0:a"] if audio_arg else ["-an"]),
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            str(out_path),
        ],
        cwd=str(ROOT), check=True,
    )

    # Cleanup annotated intermediates
    ann_a.unlink(missing_ok=True)
    ann_b.unlink(missing_ok=True)
    if audio_arg:
        tiled_audio.unlink(missing_ok=True)

    print(f"\nDone.")
    print(f"  Output : {out_path}")
    print()
    print("Timeline (both clips):")
    print(f"  t=0.000 – {CONSULT_DURATION:.1f}s   consult playing")
    print(f"  [A] t={CONSULT_DURATION:.1f}  – {CONSULT_DURATION + GLOBAL_FADE_DUR:.1f}s  fade-to-idle (global 1.0s)")
    print(f"  [B] t={CONSULT_DURATION:.1f}  – {CONSULT_DURATION + EXPLICIT_FADE_DUR:.1f}s  fade-to-idle (explicit 0.7s)")


if __name__ == "__main__":
    main()
