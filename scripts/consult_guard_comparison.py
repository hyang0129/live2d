#!/usr/bin/env python3
"""
Consult breath-guard comparison — 3 clips in one video.

Tests three strategies for smoothing the breath resumption when the consult
motion exits.  All clips use the same consult motion (AngleZ +14°, 2.5s) and
the same Cubism FadeOut window (t=1.5–2.5s, 1.0s FadeOutTime).

  Clip A — lerp_overlap     : exit ramp starts when Cubism begins FadeOut (t=1.5s).
                              Duration = FadeOutTime + exit_fade_duration = 1.5s.
                              Guard at ~0.33 when priority drops (t=2.5s).
                              Guard reaches 0 at t=3.0s.

  Clip B — post_fadeout_long: exit ramp starts when FadeOut completes (t=2.5s).
                              Duration = 2× FadeOutTime = 2.0s.
                              Guard reaches 0 at t=4.5s.

  Clip C — lerp (standard)  : exit ramp starts when FadeOut completes (t=2.5s).
                              Duration = 0.5s (breath_guard_exit_fade_duration).
                              Guard reaches 0 at t=3.0s.

Output: results/tests/sable-spec-v1.1/consult_guard_comparison.mp4
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Motion parameters (consult.motion3.json + majo.model3.json) ────────────
CONSULT_DURATION = 2.5
CONSULT_FADEOUT  = 1.0
EXIT_FADE_DUR    = 0.5   # breath_guard_exit_fade_duration default
HOLD_END         = CONSULT_DURATION - CONSULT_FADEOUT  # 1.5s
ENTRY_FADE       = 0.15
CLIP_DUR         = 9.0

# Guard parameters per clip
GUARD_A_START    = HOLD_END                            # 1.5s (arms during FadeOut)
GUARD_A_DUR      = CONSULT_FADEOUT + EXIT_FADE_DUR     # 1.5s
GUARD_A_END      = GUARD_A_START + GUARD_A_DUR         # 3.0s

GUARD_B_START    = CONSULT_DURATION                    # 2.5s (arms after FadeOut)
GUARD_B_DUR      = 2.0 * CONSULT_FADEOUT               # 2.0s
GUARD_B_END      = GUARD_B_START + GUARD_B_DUR         # 4.5s

GUARD_C_START    = CONSULT_DURATION                    # 2.5s (arms after FadeOut)
GUARD_C_DUR      = EXIT_FADE_DUR                       # 0.5s
GUARD_C_END      = GUARD_C_START + GUARD_C_DUR         # 3.0s

# ── Model IDs ────────────────────────────────────────────────────────────────
MODELS = {
    "A": "majo_consult_lerp_overlap",
    "B": "majo_consult_post_fadeout_long",
    "C": "majo_consult_lerp",
}

# ── Paths ────────────────────────────────────────────────────────────────────
AUDIO_SRC     = ROOT / "tests/fixtures/cheesetest/wav/scene_01.wav"
TMPL_MANIFEST = ROOT / "tests/fixtures/cheesetest/scene_01_manifest.json"
OUT_DIR       = ROOT / "results/tests/sable-spec-v1.1"
RENDERER      = ROOT / "build/live2d-render"

STEP = 0.1


# ── FFmpeg helpers ────────────────────────────────────────────────────────────

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


# ── Per-clip VF builders ──────────────────────────────────────────────────────

def _common_consult_lines(parts: list, label_title: str, guard_label_fn,
                          guard_start: float, guard_end: float, guard_dur: float,
                          show_suppressed_through_fo: bool = False) -> None:
    """
    Appends the shared overlay lines into `parts`.
      guard_label_fn(rem) -> string for the guard FADEOUT weight line
      guard_start / guard_end / guard_dur: guard ramp window
      show_suppressed_through_fo: if True, SUPPRESSED label extends to CONSULT_DURATION
                                  (for post-FadeOut modes where guard doesn't arm during FO)
    """
    LH = 43
    Y0 = 175

    # Top center — pass criteria
    crit = _esc("PASS: no snap at t=2.5s. Smooth tilt exit. Guard outlasts Cubism FadeOut.")
    parts.append(
        f"drawtext=text='{crit}'"
        f":fontsize=22:fontcolor=yellow"
        f":x=(w-tw)/2:y=40"
        f":box=1:boxcolor=black@0.7:boxborderw=8"
    )

    # Bottom center — clip identity
    lbl = _esc(label_title)
    parts.append(
        f"drawtext=text='{lbl}'"
        f":fontsize=28:fontcolor=white"
        f":x=(w-tw)/2:y=h-120"
        f":box=1:boxcolor=black@0.65:boxborderw=12"
    )

    # Line 1 — idle (always)
    parts.append(_dt("idle  [looping]", y_from_bottom=Y0))

    # Line 2 — consult HOLD then FADEOUT
    parts.extend(_seq(
        lambda rem: f"consult  HOLD : {rem:.1f}s remaining",
        0.0, HOLD_END, Y0 + LH, color="red",
    ))
    parts.extend(_seq(
        lambda rem: f"consult  FADEOUT : {rem:.1f}s remaining",
        HOLD_END, CONSULT_DURATION, Y0 + LH, color="red",
    ))

    # Line 3 — breath-guard status
    suppress_end = CONSULT_DURATION if show_suppressed_through_fo else HOLD_END
    if suppress_end > ENTRY_FADE:
        parts.append(_dt(
            "breath-guard  SUPPRESSED  (w=1.00)",
            y_from_bottom=Y0 + LH * 2,
            enable=_between(ENTRY_FADE, suppress_end),
            color="orange",
        ))
    parts.extend(_seq(
        guard_label_fn,
        guard_start, guard_end, Y0 + LH * 2, color="orange",
    ))

    # Line 4 — cubism-FadeOut window (always t=1.5–2.5)
    parts.extend(_seq(
        lambda rem: f"cubism-FadeOut : {rem:.1f}s  <- guard continues after",
        HOLD_END, CONSULT_DURATION, Y0 + LH * 3, color="cyan",
    ))


def build_vf_A() -> str:
    """Clip A: lerp_overlap — guard arms at t=1.5s, duration 1.5s."""
    parts = []
    _common_consult_lines(
        parts,
        label_title="CLIP A: lerp-overlap guard  (arms at FadeOut start, 1.5s ramp)",
        guard_label_fn=lambda rem: f"guard LERP-OVERLAP  w={(rem / GUARD_A_DUR):.2f}",
        guard_start=GUARD_A_START,
        guard_end=GUARD_A_END,
        guard_dur=GUARD_A_DUR,
        show_suppressed_through_fo=False,  # SUPPRESSED only to t=1.5; guard takes over at t=1.5
    )
    return ",".join(parts)


def build_vf_B() -> str:
    """Clip B: post_fadeout_long — guard arms at t=2.5s, duration 2.0s."""
    parts = []
    _common_consult_lines(
        parts,
        label_title="CLIP B: post-fadeout-long guard  (arms after FadeOut, 2.0s ramp)",
        guard_label_fn=lambda rem: f"guard POST-FO-LONG  w={(rem / GUARD_B_DUR):.2f}",
        guard_start=GUARD_B_START,
        guard_end=GUARD_B_END,
        guard_dur=GUARD_B_DUR,
        show_suppressed_through_fo=True,   # SUPPRESSED extends through FadeOut window
    )
    return ",".join(parts)


def build_vf_C() -> str:
    """Clip C: lerp (standard) — guard arms at t=2.5s, duration 0.5s."""
    parts = []
    _common_consult_lines(
        parts,
        label_title="CLIP C: standard lerp guard  (arms after FadeOut, 0.5s ramp)",
        guard_label_fn=lambda rem: f"guard LERP  w={(rem / GUARD_C_DUR):.2f}",
        guard_start=GUARD_C_START,
        guard_end=GUARD_C_END,
        guard_dur=GUARD_C_DUR,
        show_suppressed_through_fo=True,
    )
    return ",".join(parts)


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _render_clip(model_id: str, raw_path: Path, man_path: Path,
                 audio_arg: str | None, lipsync: list) -> None:
    manifest = {
        "schema_version": "1.0",
        "model":      {"id": model_id},
        "audio":      audio_arg,
        "output":     str(raw_path).replace("\\", "/"),
        "resolution": [1080, 1920],
        "fps":        30,
        "background": "#1a1a2e",
        "lipsync":    lipsync,
        "cues": [
            {"time": 0.0, "reaction": "consult"},
        ],
    }
    with open(man_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    subprocess.run([str(RENDERER), "--scene", str(man_path)], cwd=str(ROOT), check=True)
    if not raw_path.exists():
        raise FileNotFoundError(f"Renderer produced no output at {raw_path}")


def _burn_overlay(raw: Path, vf: str, out: Path, audio: bool) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(raw),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            *(["-c:a", "copy"] if audio else ["-an"]),
            str(out),
        ],
        cwd=str(ROOT),
        check=True,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp_dir = ROOT / "tests/output"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    if not RENDERER.exists():
        raise FileNotFoundError(f"Renderer not found: {RENDERER}. Run: cmake --build build")

    # Audio / lipsync
    audio_arg, lipsync = None, []
    tiled_audio = tmp_dir / "cmp_audio.wav"

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

    clips_def = [
        ("A", MODELS["A"], build_vf_A),
        ("B", MODELS["B"], build_vf_B),
        ("C", MODELS["C"], build_vf_C),
    ]

    labeled_paths = []
    for clip_id, model_id, vf_fn in clips_def:
        raw  = tmp_dir / f"cmp_raw_{clip_id}.mp4"
        man  = tmp_dir / f"cmp_manifest_{clip_id}.json"
        burn = tmp_dir / f"cmp_burn_{clip_id}.mp4"

        print(f"\nRendering clip {clip_id} ({model_id}) ...")
        _render_clip(model_id, raw, man, audio_arg, lipsync)

        print(f"Burning overlays for clip {clip_id} ...")
        _burn_overlay(raw, vf_fn(), burn, audio_arg is not None)
        raw.unlink(missing_ok=True)
        labeled_paths.append(burn)

    # Concatenate
    concat_list = tmp_dir / "cmp_concat.txt"
    with open(concat_list, "w") as fh:
        for p in labeled_paths:
            fh.write(f"file '{p}'\n")

    out_path = OUT_DIR / "consult_guard_comparison.mp4"
    print("\nConcatenating clips ...")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(out_path),
        ],
        cwd=str(ROOT),
        check=True,
    )

    # Cleanup
    for p in labeled_paths:
        p.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)
    if audio_arg:
        tiled_audio.unlink(missing_ok=True)

    print(f"\nDone.")
    print(f"  Review : {out_path}")
    print()
    print("Clip guard timeline summary:")
    print(f"  A (lerp_overlap)     : guard t={GUARD_A_START:.1f}–{GUARD_A_END:.1f}s"
          f"  w=1.00→{max(0, 1-(GUARD_A_END-CONSULT_DURATION)/GUARD_A_DUR):.2f} at t=2.5s"
          f"  → 0.00 at t={GUARD_A_END:.1f}s")
    print(f"  B (post_fadeout_long): guard t={GUARD_B_START:.1f}–{GUARD_B_END:.1f}s"
          f"  w=1.00 at t=2.5s → 0.00 at t={GUARD_B_END:.1f}s")
    print(f"  C (lerp)             : guard t={GUARD_C_START:.1f}–{GUARD_C_END:.1f}s"
          f"  w=1.00 at t=2.5s → 0.00 at t={GUARD_C_END:.1f}s")


if __name__ == "__main__":
    main()
