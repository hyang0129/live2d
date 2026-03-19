#!/usr/bin/env python3
"""
Comprehensive review render — all majo motions.

Produces a single annotated video covering:
  Section 1: All emotions (default config)
  Section 2: All reactions in sequence (default config)
  Section 3: Entry snap comparison — same deep_nod at breath-peak across 3 entry-fade values
             (entry_fade=0.001 ≈ old snap, entry_fade=0.15 default fix, entry_fade=0.4 gradual)
  Section 4: Breath amplitude comparison — default vs 2× peaks
             (validates renderer_config.json is actually read by the renderer)

Output:
  results/tests/all_motions_review/review_all_motions.mp4   (human review gate)
  results/tests/all_motions_review/_tmp/                     (intermediates)

Usage:
    cd /workspaces/hub_2/live2d
    python3 tests/render_review_all_motions.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RENDERER  = REPO_ROOT / "build" / "live2d-render"
OUT_DIR   = REPO_ROOT / "results" / "tests" / "all_motions_review"
TMP_DIR   = OUT_DIR / "_tmp"
FINAL     = OUT_DIR / "review_all_motions.mp4"

RESOLUTION = [960, 540]
FPS        = 30
BG_COLOR   = "#1a1a2e"

# Minimum clip length per CLAUDE.md convention (5s + 5s idle tail after last action)
# Each clip manages its own tail via scene_tail_duration in config.

# ── Helpers ───────────────────────────────────────────────────────────────────

def escape_drawtext(text: str) -> str:
    for c, r in [("\\", "\\\\"), ("'", "\\'"), (":", "\\:"), ("[", "\\["), ("]", "\\]")]:
        text = text.replace(c, r)
    return text


def write_config(overrides: dict, path: Path) -> None:
    """Write a renderer_config.json with the given overrides merged on top of defaults."""
    base_path = REPO_ROOT / "renderer_config.json"
    with open(base_path) as f:
        cfg = json.load(f)

    def deep_merge(base: dict, patch: dict) -> dict:
        for k, v in patch.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                deep_merge(base[k], v)
            else:
                base[k] = v
        return base

    deep_merge(cfg, overrides)
    path.write_text(json.dumps(cfg, indent=2))


def render(manifest: dict, out_mp4: Path, config_path: Path | None = None,
           label: str = "") -> bool:
    """Render a manifest to out_mp4. Returns True on success."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    manifest_path = TMP_DIR / f"{out_mp4.stem}_manifest.json"
    m = dict(manifest, output=str(out_mp4))
    manifest_path.write_text(json.dumps(m, indent=2))

    cmd = [str(RENDERER), "--scene", str(manifest_path)]
    env = os.environ.copy()

    # If a custom config is supplied, copy it to the working directory temporarily.
    # The renderer reads renderer_config.json relative to cwd.
    cwd = str(REPO_ROOT)
    tmp_cfg = None
    if config_path is not None:
        tmp_cfg = REPO_ROOT / "_tmp_renderer_config.json"
        shutil.copy(config_path, tmp_cfg)
        original_cfg = REPO_ROOT / "renderer_config.json"
        original_bak = REPO_ROOT / "_renderer_config_bak.json"
        shutil.copy(original_cfg, original_bak)
        shutil.copy(config_path, original_cfg)

    if label:
        print(f"  Rendering: {label} ...", flush=True)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    finally:
        if config_path is not None and tmp_cfg is not None:
            # Restore original config
            shutil.copy(original_bak, original_cfg)
            original_bak.unlink(missing_ok=True)
            if tmp_cfg.exists():
                tmp_cfg.unlink()

    if result.returncode != 0:
        print(f"  ERROR: renderer exited {result.returncode}", file=sys.stderr)
        print(result.stdout[-2000:], file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        return False

    size_kb = out_mp4.stat().st_size // 1024
    print(f"    → {out_mp4.name}  ({size_kb} KB)")
    return True


def annotate(raw: Path, ann: Path, line1: str, line2: str = "") -> bool:
    """Burn title card onto raw clip."""
    parts = [
        "drawbox=x=0:y=0:w=iw:h=80:color=black@0.85:t=fill",
        f"drawtext=text='{escape_drawtext(line1)}'"
        ":fontsize=22:fontcolor=white"
        ":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ":x=(w-tw)/2:y=8:box=0",
    ]
    if line2:
        parts.append(
            f"drawtext=text='{escape_drawtext(line2)}'"
            ":fontsize=14:fontcolor=#cccccc"
            ":x=(w-tw)/2:y=44:box=0"
        )
    parts.append(
        "drawtext=text='t\\=%{eif\\:t\\:d}.%{eif\\:mod(t*100\\,100)\\:d}s'"
        ":fontsize=20:fontcolor=white"
        ":x=w-tw-12:y=h-36"
        ":box=1:boxcolor=black@0.7:boxborderw=4"
    )
    vf = ",".join(parts)

    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw),
         "-vf", vf,
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-an",
         str(ann)],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: annotation failed: {result.stderr.decode(errors='replace')[-1000:]}",
              file=sys.stderr)
        return False
    return True


def make_title_card(text: str, out: Path, duration: float = 2.0) -> bool:
    """Generate a plain title card (black bg, white text)."""
    safe = escape_drawtext(text)
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:size={RESOLUTION[0]}x{RESOLUTION[1]}:rate={FPS}:duration={duration}",
            "-vf",
            f"drawtext=text='{safe}'"
            ":fontsize=32:fontcolor=white"
            ":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            ":x=(w-tw)/2:y=(h-th)/2",
            "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
            str(out),
        ],
        capture_output=True,
    )
    return result.returncode == 0


def base_manifest(**kwargs) -> dict:
    m = {
        "schema_version": "1.0",
        "model": {"id": "majo"},
        "audio": "",
        "output": "",
        "resolution": RESOLUTION,
        "fps": FPS,
        "background": BG_COLOR,
        "lipsync": [],
        "cues": [],
    }
    m.update(kwargs)
    return m


def concat(clips: list[Path], out: Path) -> bool:
    lst = TMP_DIR / "concat.txt"
    with open(lst, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(out)],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"ERROR: concat failed:\n{result.stderr.decode(errors='replace')[-1000:]}",
              file=sys.stderr)
        return False
    return True


# ── Section builders ──────────────────────────────────────────────────────────

EMOTIONS = ["neutral", "happy", "surprised", "bored", "sad", "angry", "curious", "embarrassed"]
REACTIONS = ["nod", "deep_nod", "look_away", "tap"]


def build_section1_emotions() -> list[Path]:
    """All 8 emotions, ~2s each, back to neutral at end. Default config."""
    print("\n=== Section 1: All emotions (default config) ===")

    cues = [{"time": 0.0, "emotion": "neutral"}]
    t = 1.5
    for em in EMOTIONS:
        cues.append({"time": t, "emotion": em})
        t += 2.0
    # 5-second idle at end per CLAUDE.md convention
    sentinel_t = max(t, 5.0)
    cues.append({"time": sentinel_t, "emotion": "neutral"})

    manifest = base_manifest(cues=cues)
    raw = TMP_DIR / "s1_emotions_raw.mp4"
    ann = TMP_DIR / "s1_emotions_ann.mp4"

    if not render(manifest, raw, label="Section 1 — emotions"):
        return []
    if not annotate(raw, ann,
                    "Section 1: All Emotions (default config)",
                    "neutral → happy → surprised → bored → sad → angry → curious → embarrassed → neutral"):
        return []
    return [ann]


def build_section2_reactions() -> list[Path]:
    """All reactions in sequence, neutral resets between each. Default config."""
    print("\n=== Section 2: All reactions (default config) ===")
    clips = []

    for reaction in REACTIONS:
        # Idle ~2s, fire reaction, 5s idle tail after last action
        cues = [
            {"time": 0.0, "emotion": "neutral"},
            {"time": 2.0, "reaction": reaction},
            # Sentinel at t=8.0 (last_action=2.0, +5s tail + 1s buffer = 8.0)
            {"time": 8.0, "emotion": "neutral"},
        ]
        manifest = base_manifest(cues=cues)
        raw = TMP_DIR / f"s2_{reaction}_raw.mp4"
        ann = TMP_DIR / f"s2_{reaction}_ann.mp4"

        if not render(manifest, raw, label=f"  reaction: {reaction}"):
            return []
        if not annotate(raw, ann,
                        f"Section 2: reaction={reaction}",
                        "idle 2s → fire reaction → 6s settle"):
            return []
        clips.append(ann)

    return clips


def build_section3_entry_snap() -> list[Path]:
    """
    Entry snap comparison: same deep_nod fired at breath peak (worst case for snap).
    Three variants:
      a) entry_fade=0.001  — near-instant (approximates pre-fix snap behaviour)
      b) entry_fade=0.15   — default fix
      c) entry_fade=0.40   — gradual (perceptibly slower entry suppression)

    deep_nod fires at t=3.27s ≈ half of 6.5345s AngleX cycle (near negative peak, ~−15°).
    This guarantees normalisation triggers (valid_entry ±5°) and then the entry snap
    (or smooth ramp) is clearly visible on the normalization→motion transition.
    """
    print("\n=== Section 3: Entry snap comparison (deep_nod at breath peak) ===")
    clips = []

    FIRE_T = 3.27  # ≈ half of 6.5345s cycle — AngleX near negative peak
    cues = [
        {"time": 0.0,       "emotion": "neutral"},
        {"time": FIRE_T,    "reaction": "deep_nod"},
        {"time": FIRE_T + 6.0, "emotion": "neutral"},  # 5s+ tail after last action
    ]
    manifest = base_manifest(cues=cues)

    variants = [
        (0.001, "entry_fade=0.001  (≈ old snap behaviour)",
                "Abrupt cut: head jumps to motion start on entry frame"),
        (0.15,  "entry_fade=0.15s  (default — issue #5 fix)",
                "Smooth ramp: breath suppressed gradually over 0.15s on entry"),
        (0.40,  "entry_fade=0.40s  (gradual)",
                "Slow ramp: breath suppresses gently, motion leads"),
    ]

    for fade_val, line1, line2 in variants:
        cfg_path = TMP_DIR / f"s3_cfg_fade{fade_val:.3f}.json"
        write_config({"animation": {"breath_guard_entry_fade_duration": fade_val}}, cfg_path)

        raw = TMP_DIR / f"s3_entry_fade{fade_val:.3f}_raw.mp4"
        ann = TMP_DIR / f"s3_entry_fade{fade_val:.3f}_ann.mp4"

        if not render(manifest, raw, config_path=cfg_path, label=f"  entry_fade={fade_val}"):
            return []
        if not annotate(raw, ann, f"Section 3: {line1}", line2):
            return []
        clips.append(ann)

    return clips


def build_section4_breath_amplitude() -> list[Path]:
    """
    Breath amplitude comparison: default peaks vs 2× peaks.
    Validates that renderer_config.json values are actually read by the renderer
    (if the binary were ignoring the config file, both clips would look identical).
    """
    print("\n=== Section 4: Breath amplitude comparison ===")
    clips = []

    # Long idle to make breath oscillation clearly visible (10s)
    cues = [
        {"time": 0.0,  "emotion": "neutral"},
        {"time": 10.0, "emotion": "neutral"},  # sentinel
    ]
    manifest = base_manifest(cues=cues)

    variants = [
        (None,  "Default breath amplitude  (peaks: AngleX=15, AngleY=8, AngleZ=10)",
                "Baseline — post-issue-#8 reduced range"),
        ({"breath": {"parameters": {
            "angle_x":      {"offset": 0.0, "peak": 30.0, "cycle":  6.5345, "weight": 0.5},
            "angle_y":      {"offset": 0.0, "peak": 16.0, "cycle":  3.5345, "weight": 0.5},
            "angle_z":      {"offset": 0.0, "peak": 20.0, "cycle":  5.5345, "weight": 0.5},
            "body_angle_x": {"offset": 0.0, "peak":  8.0, "cycle": 15.5345, "weight": 0.5},
            "breath":       {"offset": 0.5, "peak":  0.5, "cycle":  3.2345, "weight": 0.5},
        }}},
         "2× breath amplitude  (peaks: AngleX=30, AngleY=16, AngleZ=20)",
         "Config override — visibly larger idle sway confirms config is read"),
    ]

    for cfg_overrides, line1, line2 in variants:
        tag = "default" if cfg_overrides is None else "2x"
        cfg_path = None
        if cfg_overrides is not None:
            cfg_path = TMP_DIR / f"s4_cfg_{tag}.json"
            write_config(cfg_overrides, cfg_path)

        raw = TMP_DIR / f"s4_breath_{tag}_raw.mp4"
        ann = TMP_DIR / f"s4_breath_{tag}_ann.mp4"

        if not render(manifest, raw, config_path=cfg_path, label=f"  breath amplitude: {tag}"):
            return []
        if not annotate(raw, ann, f"Section 4: {line1}", line2):
            return []
        clips.append(ann)

    return clips


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if not RENDERER.exists():
        print(f"ERROR: renderer not found at {RENDERER}", file=sys.stderr)
        print("Build first: cmake --preset linux && cmake --build --preset linux",
              file=sys.stderr)
        sys.exit(1)

    all_clips: list[Path] = []

    # Section title cards + clips
    sections = [
        ("SECTION 1 — All Emotions",              build_section1_emotions),
        ("SECTION 2 — All Reactions",             build_section2_reactions),
        ("SECTION 3 — Entry Snap Comparison",     build_section3_entry_snap),
        ("SECTION 4 — Breath Amplitude",          build_section4_breath_amplitude),
    ]

    for title, builder in sections:
        title_card = TMP_DIR / f"title_{title[:10].replace(' ','_')}.mp4"
        if not make_title_card(title, title_card, duration=2.5):
            print(f"WARNING: could not make title card for '{title}'", file=sys.stderr)
        else:
            all_clips.append(title_card)

        clips = builder()
        if not clips:
            print(f"ERROR: section '{title}' failed to render", file=sys.stderr)
            sys.exit(1)
        all_clips.extend(clips)

    print(f"\nConcatenating {len(all_clips)} clips into {FINAL} ...")
    if not concat(all_clips, FINAL):
        sys.exit(1)

    size_mb = FINAL.stat().st_size / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"DONE  →  {FINAL}  ({size_mb:.1f} MB)")
    print(f"{'='*60}")
    print("""
Human review checklist:
  Section 1 (Emotions):
    [ ] All 8 emotions visible and distinct
    [ ] Transitions are smooth
    [ ] No expression glitches

  Section 2 (Reactions — default config):
    [ ] nod:       clean head dip, ~50% amplitude; breath resumes smoothly
    [ ] deep_nod:  full amplitude nod; normalisation visible if at breath peak
    [ ] look_away: eyes/head shift right then return
    [ ] tap:       damped lateral oscillation

  Section 3 (Entry snap comparison — CRITICAL for issue #5):
    [ ] entry_fade=0.001: head visibly snaps on motion entry (one-frame jump)
    [ ] entry_fade=0.15:  clean smooth entry — NO visible snap
    [ ] entry_fade=0.40:  gradual breath fade-out, motion leads slightly

  Section 4 (Breath amplitude — CRITICAL for issue #7/PR #9):
    [ ] Default clip: modest idle sway (AngleX peak ≈15°)
    [ ] 2× clip:      clearly larger sway (AngleX peak ≈30°)
    [ ] If both clips look identical, renderer_config.json is NOT being read
""")


if __name__ == "__main__":
    main()
