from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, HttpUrl


# ---------------------------------------------------------------------------
# Model / Registry schemas
# ---------------------------------------------------------------------------

class ModelSummary(BaseModel):
    id: str
    emotions: list[str]
    reactions: list[str]


class ModelDetail(BaseModel):
    id: str
    emotions: dict[str, str]   # alias -> note
    reactions: dict[str, str]  # alias -> note


# ---------------------------------------------------------------------------
# Scene manifest (inbound, from director)
# Matches the CLI manifest schema exactly so the server can write it directly.
# ---------------------------------------------------------------------------

class ModelRef(BaseModel):
    id: str


class LipSyncEntry(BaseModel):
    time: float
    mouth_shape: str  # A-H or X


class GazeTarget(BaseModel):
    x: float = 0.0
    y: float = 0.0


class HeadAngle(BaseModel):
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0


class Cue(BaseModel):
    time: float
    emotion: str | None = None
    reaction: str | None = None
    gaze: GazeTarget | None = None
    head: HeadAngle | None = None


class SceneManifest(BaseModel):
    schema_version: str = "1.0"
    model: ModelRef
    audio_url: HttpUrl                              # server downloads this
    resolution: tuple[int, int] = (1080, 1920)
    fps: int = 30
    background: str = "transparent"
    lipsync: list[LipSyncEntry] = Field(default_factory=list)
    cues: list[Cue] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Render job schemas
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    queued = "queued"
    downloading_audio = "downloading_audio"
    rendering = "rendering"
    complete = "complete"
    failed = "failed"


class SubmitResponse(BaseModel):
    job_id: str
    status: JobStatus
    poll_url: str
    estimate_seconds: int
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float | None = None
    estimate_seconds: int | None = None
    message: str | None = None
    output_url: str | None = None
    duration_seconds: float | None = None
    log_url: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str
    renderer_available: bool
    disk_free_gb: float
    active_jobs: int
    queued_jobs: int
