#!/usr/bin/env python3
"""
verify_build.py  —  Build verification for the Live2D renderer.

Renders a short shiori test clip (3 emotions × 5 s = 15 s, ~450 frames)
and runs automated checks on the output.  A human should also visually
review the produced video to confirm correct rendering.

What is checked
---------------
  • Renderer binary is present (build is complete)
  • FFmpeg / ffprobe are on PATH
  • Required test fixtures exist (audio, manifest template, model registry)
  • FrameworkShaders directory is present (post-build copy step ran)
  • Renderer exits 0
  • Renderer log contains no known error signatures (see below)
  • Renderer log reports the expected frame count
  • Renderer log contains no unexpected WARN lines
  • Output file exists and is above the size threshold
  • Output video stream has correct dimensions and approximate duration
  • Output file contains an audio stream

Known failure signatures
------------------------
  Pattern in renderer stdout/stderr → root cause that was previously seen:

  "GLEW init failed"
      System libGLEW (Ubuntu 22.04) is compiled for GLX only and fails when
      used with an EGL context.  The GLEW shim at src/gl_compat/GL/glew.h
      must take precedence over the system header (BEFORE include path).

  "eglCreateContext failed"
      EGL 1.5 / KHR_create_context not supported by the driver, or the
      compatibility-profile bit (0x00000002) was rejected.  Check driver.

  "eglCreatePbufferSurface failed"
      EGL pbuffer extension unavailable.  Check EGL driver / Mesa version.

  "Failed to spawn ffmpeg" / "popen" in an error context
      popen() was called with mode "wb" instead of "w".  POSIX only accepts
      "r" or "w"; "wb" returns EINVAL on Linux.

  "Cannot load texture" / stb_image errors
      Texture paths are wrong, or the STB_IMAGE_IMPLEMENTATION define is
      missing from the Linux branch of live2d_model.cpp.

  "Cannot load model" / missing .model3.json
      Model path in registry is incorrect, or model files are absent.

  File too small (< MIN_FILE_SIZE threshold)
      This is the primary indicator of the blank-screen failure: when the
      EGL context was created with a Core profile instead of a Compatibility
      profile, the Cubism GLSL 1.20 shaders failed silently and every frame
      was blank.  The successful shiori_review.mp4 (1529 frames) was 2.9 MB;
      the blank version was 0.6 MB — about 5× smaller.  For our 450-frame
      test, a correctly rendered clip should be well above MIN_FILE_SIZE.

Exit codes
----------
  0  — all checks passed  (still review the video visually)
  1  — critical failure   (render failed, output missing, or fatal error)
  2  — render succeeded but warnings detected (possible visual issues)

Usage
-----
  python scripts/verify_build.py
  python scripts/verify_build.py --output tests/output/verify_shiori.mp4
  python scripts/verify_build.py --keep-intermediates
"""

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT              = Path(__file__).resolve().parent.parent
TEMPLATE_AUDIO    = ROOT / "tests/fixtures/cheesetest/wav/scene_01.wav"
TEMPLATE_MANIFEST = ROOT / "tests/fixtures/cheesetest/scene_01_manifest.json"
REGISTRY_PATH     = ROOT / "assets/models/registry.json"
FRAMEWORK_SHADERS = ROOT / "FrameworkShaders"

MODEL_ID = "shiori"

# 3 emotions × 5 s = 15 s  —  quick but covers expression-change logic
BEHAVIORS: list[tuple[str, str]] = [
    ("emotion", "neutral"),
    ("emotion", "happy"),
    ("emotion", "sad"),
]
BEHAVIOR_DUR = 5.0
TOTAL_DUR    = BEHAVIOR_DUR * len(BEHAVIORS)  # 15.0 s

# File-size threshold (bytes).
# Known-bad baseline: blank-screen render produced ~0.6 MB for 1529 frames
# → scaled to 450 frames ≈ 177 KB.  A correctly rendered 450-frame clip at
# 1080×1920 should be well above 400 KB.
MIN_FILE_SIZE = 400_000  # 400 KB

# ── state collectors ──────────────────────────────────────────────────────────

WARNINGS: list[str] = []
ERRORS:   list[str] = []
PASSED:   list[str] = []


def _warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"  WARN   {msg}")


def _error(msg: str) -> None:
    ERRORS.append(msg)
    print(f"  ERROR  {msg}")


def _ok(msg: str) -> None:
    PASSED.append(msg)
    print(f"  OK     {msg}")


def _section(title: str) -> None:
    width = 60
    print(f"\n── {title} {'─' * max(0, width - len(title) - 4)}")


# ── preflight ─────────────────────────────────────────────────────────────────

def check_preflight() -> bool:
    _section("Preflight checks")
    all_ok = True

    # Renderer binary
    if platform.system() == "Windows":
        renderer = ROOT / "build" / "Release" / "live2d-render.exe"
    else:
        renderer = ROOT / "build" / "live2d-render"

    if renderer.exists():
        _ok(f"Renderer binary: {renderer.relative_to(ROOT)}")
    else:
        _error(f"Renderer binary not found: {renderer.relative_to(ROOT)}")
        _error("  → Run: cmake --preset linux && cmake --build --preset linux")
        all_ok = False

    # FFmpeg
    if shutil.which("ffmpeg"):
        _ok("ffmpeg on PATH")
    else:
        _error("ffmpeg not found on PATH — install: sudo apt install ffmpeg")
        all_ok = False

    # ffprobe (optional but preferred)
    if shutil.which("ffprobe"):
        _ok("ffprobe on PATH")
    else:
        _warn("ffprobe not found — video stream checks will be skipped")

    # FrameworkShaders (post-build copy step)
    if FRAMEWORK_SHADERS.is_dir() and any(FRAMEWORK_SHADERS.iterdir()):
        _ok(f"FrameworkShaders directory present ({len(list(FRAMEWORK_SHADERS.iterdir()))} files)")
    else:
        _error(
            "FrameworkShaders/ directory missing or empty. "
            "This is copied from the SDK by a CMake POST_BUILD step. "
            "Re-run the build to trigger it."
        )
        all_ok = False

    # Test fixtures
    for path, label in [
        (TEMPLATE_AUDIO,    "Template audio"),
        (TEMPLATE_MANIFEST, "Template manifest"),
        (REGISTRY_PATH,     "Model registry"),
    ]:
        if path.exists():
            _ok(f"{label}: {path.relative_to(ROOT)}")
        else:
            _error(f"{label} not found: {path.relative_to(ROOT)}")
            all_ok = False

    # Shiori entry in registry
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH, encoding="utf-8") as fh:
            registry = json.load(fh)
        entry = next((m for m in registry if m["id"] == MODEL_ID), None)
        if entry:
            _ok(f"Model '{MODEL_ID}' in registry")
        else:
            ids = [m["id"] for m in registry]
            _error(f"Model '{MODEL_ID}' not in registry. Available: {ids}")
            all_ok = False

    return all_ok


# ── manifest & audio helpers ──────────────────────────────────────────────────

def _tile_audio(src: Path, dest: Path, total_dur: float) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
         "-t", f"{total_dur:.3f}", "-c", "copy", str(dest)],
        capture_output=True, check=True,
    )


def _tile_lipsync(keyframes: list, loop_dur: float, total_dur: float) -> list:
    tiled, i = [], 0
    while (offset := i * loop_dur) < total_dur:
        for kf in keyframes:
            t = round(kf["time"] + offset, 4)
            if t >= total_dur:
                break
            tiled.append({"time": t, "mouth_shape": kf["mouth_shape"]})
        i += 1
    return tiled


def build_manifest(out_dir: Path) -> tuple[Path, Path, Path]:
    """Build manifest, tile audio, return (manifest_path, raw_output_path, tiled_audio_path)."""
    with open(TEMPLATE_MANIFEST, encoding="utf-8") as fh:
        tmpl = json.load(fh)

    template_lipsync = tmpl.get("lipsync", [])
    max_t    = max((kf["time"] for kf in template_lipsync), default=0.0)
    loop_dur = max_t + 1.0

    tiled_audio_path = out_dir / "verify_shiori_audio.wav"
    print(f"  Tiling audio ({TOTAL_DUR:.0f}s) ...")
    _tile_audio(TEMPLATE_AUDIO, tiled_audio_path, TOTAL_DUR)

    tiled_lipsync = _tile_lipsync(template_lipsync, loop_dur, TOTAL_DUR)

    # Build cues: one per behavior + terminal hold
    cues = []
    for idx, (cue_key, cue_val) in enumerate(BEHAVIORS):
        cues.append({"time": round(idx * BEHAVIOR_DUR, 3), cue_key: cue_val})
    terminal_t = round(TOTAL_DUR - 1.0, 3)
    if terminal_t > cues[-1]["time"]:
        last_key, last_val = BEHAVIORS[-1]
        cues.append({"time": terminal_t, last_key: last_val})

    raw_path = out_dir / "verify_shiori_raw.mp4"
    manifest = {
        "schema_version": "1.0",
        "model":      {"id": MODEL_ID},
        "audio":      str(tiled_audio_path).replace("\\", "/"),
        "output":     str(raw_path).replace("\\", "/"),
        "resolution": tmpl.get("resolution", [1080, 1920]),
        "fps":        tmpl.get("fps", 30),
        "background": "#1a1a2e",
        "lipsync":    tiled_lipsync,
        "cues":       cues,
    }

    manifest_path = out_dir / "verify_shiori_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    return manifest_path, raw_path, tiled_audio_path


# ── renderer ──────────────────────────────────────────────────────────────────

def run_renderer(manifest_path: Path) -> tuple[int, str]:
    """Return (returncode, combined stdout+stderr)."""
    if platform.system() == "Windows":
        renderer = ROOT / "build" / "Release" / "live2d-render.exe"
    else:
        renderer = ROOT / "build" / "live2d-render"

    result = subprocess.run(
        [str(renderer), "--scene", str(manifest_path)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.returncode, result.stdout


# ── log analysis ──────────────────────────────────────────────────────────────

# (pattern, human-readable explanation of root cause)
_KNOWN_ERROR_PATTERNS: list[tuple[str, str]] = [
    (
        r"GLEW init failed",
        "System libGLEW is compiled for GLX only and fails with EGL contexts. "
        "The GLEW shim at src/gl_compat/GL/glew.h must take precedence — check "
        "that BEFORE include path is set in CMakeLists.txt."
    ),
    (
        r"eglCreateContext failed",
        "EGL context creation failed. The build may be requesting a Core profile "
        "instead of a Compatibility profile (required for GLSL 1.20 shaders). "
        "Check offscreen_opengl.cpp ctx_attrs for 0x30FD=0x00000002."
    ),
    (
        r"eglCreatePbufferSurface failed",
        "EGL pbuffer surface unavailable. Check EGL driver / Mesa version."
    ),
    (
        r"eglInitialize failed|eglGetDisplay.*failed",
        "EGL initialisation failed. No EGL-capable GPU/driver found. "
        "On a server, check that Mesa or a GPU driver is installed."
    ),
    (
        r"Failed to spawn ffmpeg|popen.*fail|pipe.*fail",
        "FFmpeg pipe failed to open. On Linux, popen() mode must be 'w' not "
        "'wb' (POSIX rejects 'wb' with EINVAL). Check ffmpeg_encoder.cpp."
    ),
    (
        r"stbi_load|Cannot load texture|texture.*fail",
        "Texture loading failed. Check that stb_image.h is on the include path "
        "and STB_IMAGE_IMPLEMENTATION is defined in live2d_model.cpp (Linux branch)."
    ),
    (
        r"Cannot load model|model3\.json.*not found|failed to open.*model",
        "Model file not found. Check the path in registry.json and that the "
        "model assets are present under assets/models/."
    ),
    (
        r"Shader.*error|glCompileShader|GLSL|version.*not supported",
        "Shader compilation error. Cubism uses GLSL 1.20 (attribute/varying/"
        "gl_FragColor) which requires a Compatibility profile context. "
        "Check EGL context creation in offscreen_opengl.cpp."
    ),
]


def check_renderer_log(log: str, fps: int) -> None:
    _section("Renderer log analysis")

    for line in log.strip().splitlines():
        print(f"    {line}")
    print()

    # Known error patterns
    for pattern, explanation in _KNOWN_ERROR_PATTERNS:
        if re.search(pattern, log, re.IGNORECASE | re.MULTILINE):
            _warn(f"Known failure pattern matched: '{pattern}'")
            _warn(f"  Root cause: {explanation}")

    # Render complete + frame count
    m = re.search(r"Render complete:\s*(\d+)\s*frames", log)
    if m:
        rendered = int(m.group(1))
        # Renderer adds a 1-second tail; expect TOTAL_DUR+1 seconds of frames ± 10%
        expected_approx = int((TOTAL_DUR + 1.0) * fps)
        if rendered < expected_approx * 0.80:
            _warn(
                f"Rendered only {rendered} frames; expected ~{expected_approx}. "
                f"Render may have terminated early."
            )
        else:
            _ok(f"Rendered {rendered} frames (expected ~{expected_approx})")
    else:
        _warn(
            "No 'Render complete' line found in renderer output. "
            "Render may not have finished successfully."
        )

    # WARN lines from renderer (unknown expression/motion names etc.)
    warn_lines = [l for l in log.splitlines() if re.search(r"\bWARN\b", l)]
    if warn_lines:
        _warn(f"Renderer emitted {len(warn_lines)} WARN line(s) — cue names may be wrong:")
        for line in warn_lines[:5]:
            _warn(f"  {line.strip()}")
    else:
        _ok("No WARN lines in renderer output")


# ── output file checks ────────────────────────────────────────────────────────

def check_output_file(raw_path: Path, fps: int, resolution: list) -> None:
    _section("Output file checks")

    if not raw_path.exists():
        _error(f"Output file does not exist: {raw_path.name}")
        return

    size    = raw_path.stat().st_size
    size_kb = size / 1024

    if size < MIN_FILE_SIZE:
        _warn(
            f"Output file is suspiciously small: {size_kb:.0f} KB "
            f"(threshold: {MIN_FILE_SIZE // 1024} KB). "
            f"This is the primary symptom of the blank-screen failure — "
            f"model rendered as blank frames (Core profile vs Compatibility profile). "
            f"Check that offscreen_opengl.cpp requests a Compatibility context."
        )
    else:
        _ok(f"Output file size: {size_kb:.0f} KB (above {MIN_FILE_SIZE // 1024} KB threshold)")

    # ffprobe video stream checks
    if not shutil.which("ffprobe"):
        _warn("ffprobe not on PATH — skipping video stream checks")
        return

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(raw_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _warn(f"ffprobe failed: {result.stderr.strip()[:200]}")
        return

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError:
        _warn("ffprobe returned unparseable JSON")
        return

    streams = info.get("streams", [])
    video   = [s for s in streams if s.get("codec_type") == "video"]
    audio   = [s for s in streams if s.get("codec_type") == "audio"]

    if not video:
        _error("No video stream in output file")
        return

    vs = video[0]

    # Resolution
    w, h = vs.get("width", 0), vs.get("height", 0)
    exp_w, exp_h = resolution[0], resolution[1]
    if w == exp_w and h == exp_h:
        _ok(f"Video resolution: {w}×{h}")
    else:
        _warn(f"Unexpected resolution: got {w}×{h}, expected {exp_w}×{exp_h}")

    # Duration
    dur_raw = vs.get("duration") or info.get("format", {}).get("duration", "0")
    try:
        actual_dur = float(dur_raw)
    except (ValueError, TypeError):
        actual_dur = 0.0

    expected_dur = TOTAL_DUR + 1.0  # renderer adds 1 s tail
    if actual_dur < 1.0:
        _warn(f"Video duration is effectively zero ({actual_dur:.2f}s) — file may be corrupt")
    elif abs(actual_dur - expected_dur) > 3.0:
        _warn(
            f"Unexpected duration: {actual_dur:.1f}s (expected ~{expected_dur:.1f}s). "
            f"Render may have terminated early."
        )
    else:
        _ok(f"Video duration: {actual_dur:.1f}s (expected ~{expected_dur:.1f}s)")

    # Frame count (not always populated by FFmpeg without full decode)
    nb_frames_str = vs.get("nb_frames")
    if nb_frames_str and nb_frames_str != "N/A":
        nb_frames     = int(nb_frames_str)
        expected_approx = int(expected_dur * fps)
        if nb_frames < expected_approx * 0.80:
            _warn(f"Frame count low: {nb_frames} (expected ~{expected_approx})")
        else:
            _ok(f"Frame count: {nb_frames} (expected ~{expected_approx})")

    # Audio stream
    if audio:
        _ok("Audio stream present")
    else:
        _warn("No audio stream in output — lipsync audio may not have been mixed in")


# ── label burn ────────────────────────────────────────────────────────────────

def burn_labels(raw_path: Path, final_path: Path) -> bool:
    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")

    parts = []
    for i, (_, cue_val) in enumerate(BEHAVIORS):
        t0 = i * BEHAVIOR_DUR
        t1 = (i + 1) * BEHAVIOR_DUR
        e  = escape(cue_val)
        parts.append(
            f"drawtext=text='{e}'"
            f":enable='between(t\\,{t0:.3f}\\,{t1:.3f})'"
            f":fontsize=36:fontcolor=white"
            f":x=(w-tw)/2:y=h-120"
            f":box=1:boxcolor=black@0.65:boxborderw=14"
        )
    vf = ",".join(parts)

    result = subprocess.run(
        ["ffmpeg", "-y",
         "-i", str(raw_path),
         "-vf", vf,
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "copy",
         str(final_path)],
        cwd=str(ROOT),
        capture_output=True,
    )
    return result.returncode == 0


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Render a shiori verification clip and check for known failure signatures. "
            "Always visually review the produced video as a final confirmation."
        )
    )
    parser.add_argument(
        "--output", default=None,
        help="Final labeled output path (default: tests/output/verify_shiori.mp4)",
    )
    parser.add_argument(
        "--keep-intermediates", action="store_true",
        help="Keep intermediate files (raw render, tiled audio, manifest)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Live2D Renderer — Build Verification")
    print(f"  Model: {MODEL_ID}  |  Behaviors: neutral, happy, sad")
    print(f"  Duration: {TOTAL_DUR:.0f}s  |  FPS: 30  |  ~{int((TOTAL_DUR+1)*30)} frames")
    print("=" * 60)

    # ── preflight ──────────────────────────────────────────────────────────
    if not check_preflight():
        _section("Result")
        print("\n  FAILED — preflight checks did not pass.")
        print("  Fix the errors above before attempting a render.\n")
        sys.exit(1)

    # ── output dir ─────────────────────────────────────────────────────────
    out_dir = ROOT / "tests" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = Path(args.output) if args.output else out_dir / "verify_shiori.mp4"

    # ── build manifest ─────────────────────────────────────────────────────
    _section("Building test manifest")
    manifest_path, raw_path, tiled_audio_path = build_manifest(out_dir)
    print(f"  Manifest : {manifest_path.relative_to(ROOT)}")

    # ── render ─────────────────────────────────────────────────────────────
    with open(TEMPLATE_MANIFEST, encoding="utf-8") as fh:
        tmpl = json.load(fh)
    fps = tmpl.get("fps", 30)

    _section(f"Rendering ({MODEL_ID}, {TOTAL_DUR:.0f}s, {fps} fps)")
    print("  This may take 10–30 seconds ...")
    returncode, log_output = run_renderer(manifest_path)

    # ── log analysis ───────────────────────────────────────────────────────
    check_renderer_log(log_output, fps)

    if returncode != 0:
        _error(f"Renderer exited with code {returncode}")
        _section("Result")
        print("\n  FAILED — renderer did not complete successfully.")
        print("  See renderer output above for details.\n")
        sys.exit(1)
    else:
        _ok(f"Renderer exit code: 0")

    # ── output checks ──────────────────────────────────────────────────────
    resolution = tmpl.get("resolution", [1080, 1920])
    check_output_file(raw_path, fps, resolution)

    # ── burn labels ────────────────────────────────────────────────────────
    _section("Burning behavior labels")
    if burn_labels(raw_path, final_path):
        _ok(f"Final output: {final_path.relative_to(ROOT)}")
    else:
        _warn("Label burn step failed — raw output preserved without labels")
        final_path = raw_path  # fall back

    # ── cleanup intermediates ──────────────────────────────────────────────
    if not args.keep_intermediates:
        for p in [raw_path, tiled_audio_path, manifest_path]:
            if p.exists() and p != final_path:
                p.unlink()

    # ── summary ────────────────────────────────────────────────────────────
    _section("Summary")
    print(f"  Passed   : {len(PASSED)}")
    print(f"  Warnings : {len(WARNINGS)}")
    print(f"  Errors   : {len(ERRORS)}")

    if ERRORS:
        print("\n  RESULT: FAILED")
        if final_path.exists():
            print(f"\n  Partial output (if any): {final_path}")
        print()
        sys.exit(1)

    if WARNINGS:
        print("\n  RESULT: PASSED WITH WARNINGS")
        print(f"\n  Open the output and visually confirm:")
        print(f"    • Shiori model is visible (not a blank/blue screen)")
        print(f"    • Expression changes are visible at each labeled segment")
        print(f"    • Lip sync mouth movement is present")
        print(f"\n  Output: {final_path}\n")
        sys.exit(2)

    print("\n  RESULT: PASSED")
    print(f"\n  Visually verify the output before signing off on the build:")
    print(f"    • Shiori model is visible (not a blank or solid-color screen)")
    print(f"    • 'neutral' → 'happy' → 'sad' expression changes are visible")
    print(f"    • Lip sync mouth movement is present throughout")
    print(f"\n  Output: {final_path}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
