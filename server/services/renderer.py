"""Subprocess wrapper around the live2d-render CLI."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..config import settings

# Pattern emitted by the renderer: "Frame 405/900"
_FRAME_RE = re.compile(r"Frame\s+(\d+)/(\d+)", re.IGNORECASE)


@dataclass
class RenderResult:
    returncode: int
    log: str
    total_frames: int = 0
    rendered_frames: int = 0

    @property
    def success(self) -> bool:
        return self.returncode == 0


async def run_render(
    manifest_path: Path,
    log_path: Path,
    progress_cb=None,  # async callable(float)
) -> RenderResult:
    """
    Run live2d-render as a subprocess.

    progress_cb is called with a float [0.0, 1.0] each time a new frame
    line is parsed from stdout/stderr.
    """
    cmd = [str(settings.binary_path), "--scene", str(manifest_path)]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    log_lines: list[str] = []
    rendered = 0
    total = 0

    assert proc.stdout is not None
    async for raw_line in proc.stdout:
        line = raw_line.decode(errors="replace").rstrip()
        log_lines.append(line)

        m = _FRAME_RE.search(line)
        if m:
            rendered = int(m.group(1))
            total = int(m.group(2))
            if progress_cb and total > 0:
                await progress_cb(rendered / total)

    await proc.wait()

    log_text = "\n".join(log_lines)
    log_path.write_text(log_text, encoding="utf-8")

    return RenderResult(
        returncode=proc.returncode or 0,
        log=log_text,
        total_frames=total,
        rendered_frames=rendered,
    )
