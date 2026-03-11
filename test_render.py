#!/usr/bin/env python3
"""
End-to-end test render.

Starts the FastAPI server in-process, serves the test WAV over a tiny HTTP
server, submits a render job, polls until done, and reports the output path.

Usage:
    python test_render.py [--scene N]   # N = 1..6, default 1
    python test_render.py --direct      # skip server, call CLI directly
"""

import argparse
import asyncio
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent

# Locate test assets
FIXTURES = ROOT / "tests" / "fixtures" / "cheesetest"
WAV_DIR  = FIXTURES / "wav"


# ---------------------------------------------------------------------------
# Tiny static file server for WAV files
# ---------------------------------------------------------------------------

def start_file_server(directory: Path) -> tuple[str, threading.Thread]:
    """Serve files from *directory* on a random port. Returns (base_url, thread)."""
    handler = http.server.SimpleHTTPRequestHandler

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, fmt, *args):  # suppress request logs
            pass

    import socketserver
    server = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return f"http://127.0.0.1:{port}", server


# ---------------------------------------------------------------------------
# Direct CLI test (no server)
# ---------------------------------------------------------------------------

def test_direct(scene: int):
    manifest_path = FIXTURES / f"scene_0{scene}_manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found")
        sys.exit(1)

    # Rewrite manifest to a temp file with absolute paths and a temp output
    with open(manifest_path) as f:
        mf = json.load(f)

    wav_file = WAV_DIR / f"scene_0{scene}.wav"
    if not wav_file.exists():
        print(f"ERROR: WAV file not found: {wav_file}")
        sys.exit(1)

    out_dir = ROOT / "renders" / "test_direct"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"scene_0{scene}.mp4"

    mf["audio"] = str(wav_file)
    mf["output"] = str(out_file)

    tmp = tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False)
    json.dump(mf, tmp, indent=2)
    tmp.close()

    binary = ROOT / "build" / "live2d-render"
    if not binary.exists():
        print(f"ERROR: Renderer binary not found at {binary}")
        print("Build first: cmake --preset linux && cmake --build build/")
        sys.exit(1)

    print(f"Running: {binary} --scene {tmp.name}")
    print(f"Output:  {out_file}")
    print()

    result = subprocess.run(
        [str(binary), "--scene", tmp.name],
        capture_output=False,  # let output stream to terminal
    )
    os.unlink(tmp.name)

    if result.returncode == 0:
        print(f"\nSUCCESS — output: {out_file}")
        if out_file.exists():
            mb = out_file.stat().st_size / 1024 / 1024
            print(f"File size: {mb:.1f} MB")
    else:
        print(f"\nFAILED — exit code {result.returncode}")
        sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# Full server test
# ---------------------------------------------------------------------------

def test_via_server(scene: int):
    # Lazy import — needs dependencies installed
    try:
        import httpx
        import uvicorn
    except ImportError:
        print("ERROR: Missing dependencies. Run: pip install -r requirements.txt")
        sys.exit(1)

    wav_file = WAV_DIR / f"scene_0{scene}.wav"
    if not wav_file.exists():
        print(f"ERROR: WAV file not found: {wav_file}")
        sys.exit(1)

    manifest_path = FIXTURES / f"scene_0{scene}_manifest.json"
    with open(manifest_path) as f:
        original = json.load(f)

    # Start WAV file server
    base_url, wav_server = start_file_server(WAV_DIR)
    audio_url = f"{base_url}/scene_0{scene}.wav"
    print(f"WAV server:  {audio_url}")

    # Configure server to use the test binary
    os.environ.setdefault("RENDER_BINARY", str(ROOT / "build" / "live2d-render"))
    os.environ.setdefault("RENDER_OUTPUT_DIR", str(ROOT / "renders"))
    os.environ.setdefault("API_KEY", "")

    # Start FastAPI in a background thread
    from server.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=18443, log_level="warning")
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    base = "http://127.0.0.1:18443"
    for _ in range(30):
        try:
            r = httpx.get(f"{base}/health", timeout=1)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.2)
    else:
        print("ERROR: Server did not start in time")
        sys.exit(1)

    print("Server ready.")

    # Build server-format manifest from the original
    server_manifest = {
        "schema_version": original.get("schema_version", "1.0"),
        "model": {"id": original["model"]["id"]},
        "audio_url": audio_url,
        "resolution": original.get("resolution", [1080, 1920]),
        "fps": original.get("fps", 30),
        "background": original.get("background", "transparent"),
        "lipsync": original.get("lipsync", []),
        "cues": original.get("cues", []),
    }

    print(f"Submitting render for scene {scene} (model: {server_manifest['model']['id']})...")
    resp = httpx.post(f"{base}/renders", json=server_manifest, timeout=10)
    if resp.status_code != 202:
        print(f"ERROR: Submit failed {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    job_id = data["job_id"]
    print(f"Job ID:      {job_id}")
    print(f"Polling:     {base}/renders/{job_id}")
    print()

    # Poll until done
    start = time.time()
    while True:
        status_resp = httpx.get(f"{base}/renders/{job_id}", timeout=5)
        status = status_resp.json()
        s = status["status"]
        progress = status.get("progress")
        elapsed = time.time() - start

        if progress is not None:
            bar_width = 30
            filled = int(bar_width * progress)
            bar = "#" * filled + "-" * (bar_width - filled)
            print(f"\r[{bar}] {progress*100:.0f}%  {elapsed:.0f}s elapsed  ", end="", flush=True)
        else:
            print(f"\r{s}  {elapsed:.0f}s elapsed  ", end="", flush=True)

        if s == "complete":
            print()
            dur = status.get("duration_seconds", "?")
            print(f"\nSUCCESS in {dur}s")
            print(f"Output:   {base}{status['output_url']}")
            print(f"Log:      {base}{status['log_url']}")
            out_path = ROOT / "renders" / job_id / "output.mp4"
            if out_path.exists():
                mb = out_path.stat().st_size / 1024 / 1024
                print(f"Local:    {out_path}  ({mb:.1f} MB)")
            break
        elif s == "failed":
            print()
            print(f"\nFAILED: {status.get('error', '(no error message)')}")
            log_url = status.get("log_url")
            if log_url:
                log = httpx.get(f"{base}{log_url}").text
                print("\n--- render.log ---")
                print(log[-3000:])
            sys.exit(1)

        time.sleep(2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test render pipeline")
    parser.add_argument("--scene", type=int, default=1, choices=range(1, 7),
                        help="Cheesetest scene number (1-6, default: 1)")
    parser.add_argument("--direct", action="store_true",
                        help="Call the CLI directly instead of going through the server")
    args = parser.parse_args()

    if args.direct:
        test_direct(args.scene)
    else:
        test_via_server(args.scene)
