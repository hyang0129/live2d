"""In-memory job queue + asyncio worker pool."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import httpx

from ..config import settings
from ..schemas import JobStatus, SceneManifest
from .renderer import run_render

# Rough estimate: ms per frame at 1080p30
_MS_PER_FRAME_ESTIMATE = 200  # conservative


@dataclass
class Job:
    job_id: str
    manifest: SceneManifest
    status: JobStatus = JobStatus.queued
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None

    @property
    def job_dir(self) -> Path:
        return settings.output_dir / self.job_id

    @property
    def manifest_path(self) -> Path:
        return self.job_dir / "manifest.json"

    @property
    def audio_path(self) -> Path:
        return self.job_dir / "audio.wav"

    @property
    def output_path(self) -> Path:
        return self.job_dir / "output.mp4"

    @property
    def log_path(self) -> Path:
        return self.job_dir / "render.log"

    def estimate_seconds(self) -> int:
        """Naive estimate based on elapsed time and frame progress."""
        if self.status == JobStatus.rendering and self.progress > 0 and self.started_at:
            elapsed = time.time() - self.started_at
            remaining = (elapsed / self.progress) - elapsed
            return max(1, int(remaining))
        return 120

    def duration_seconds(self) -> float | None:
        if self.started_at and self.finished_at:
            return round(self.finished_at - self.started_at, 1)
        return None


class JobManager:
    def __init__(self):
        self.jobs: dict[str, Job] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._running = False

    async def start(self):
        self._running = True
        for _ in range(settings.render_workers):
            task = asyncio.create_task(self._worker())
            self._workers.append(task)

    async def stop(self):
        self._running = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)

    def submit(self, manifest: SceneManifest) -> Job:
        job_id = "r_" + uuid.uuid4().hex
        job = Job(job_id=job_id, manifest=manifest)
        self.jobs[job_id] = job
        self._queue.put_nowait(job_id)
        return job

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    async def _worker(self):
        while self._running:
            try:
                job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            job = self.jobs.get(job_id)
            if job is None:
                continue

            try:
                await self._run_job(job)
            except Exception as exc:
                job.status = JobStatus.failed
                job.error = str(exc)
                job.finished_at = time.time()

    async def _run_job(self, job: Job):
        job.job_dir.mkdir(parents=True, exist_ok=True)
        job.started_at = time.time()

        # 1. Download audio
        job.status = JobStatus.downloading_audio
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(str(job.manifest.audio_url))
                resp.raise_for_status()
                job.audio_path.write_bytes(resp.content)
        except Exception as exc:
            raise RuntimeError(f"Audio download failed: {exc}") from exc

        # 2. Write manifest in CLI format (audio/output are local paths, no audio_url)
        m = job.manifest
        cli_manifest = {
            "schema_version": m.schema_version,
            "model": {"id": m.model.id},
            "audio": str(job.audio_path),
            "output": str(job.output_path),
            "resolution": list(m.resolution),
            "fps": m.fps,
            "background": m.background,
            "lipsync": [{"time": ls.time, "mouth_shape": ls.mouth_shape} for ls in m.lipsync],
            "cues": [
                {k: v for k, v in {
                    "time": c.time,
                    "emotion": c.emotion,
                    "reaction": c.reaction,
                    "gaze": c.gaze.model_dump() if c.gaze else None,
                    "head": c.head.model_dump() if c.head else None,
                }.items() if v is not None}
                for c in m.cues
            ],
        }
        job.manifest_path.write_text(json.dumps(cli_manifest, indent=2))

        # 3. Run renderer
        job.status = JobStatus.rendering

        async def on_progress(p: float):
            job.progress = p

        result = await run_render(
            manifest_path=job.manifest_path,
            log_path=job.log_path,
            progress_cb=on_progress,
        )

        job.finished_at = time.time()

        if result.success:
            job.status = JobStatus.complete
            job.progress = 1.0
        else:
            job.status = JobStatus.failed
            last_lines = "\n".join(result.log.splitlines()[-10:])
            job.error = f"Renderer exited with code {result.returncode}. Last output:\n{last_lines}"


job_manager = JobManager()
