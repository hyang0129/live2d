import shutil

from fastapi import APIRouter

from ..config import settings
from ..schemas import HealthResponse
from ..services.job_manager import job_manager

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    renderer_available = settings.binary_path.exists()

    disk = shutil.disk_usage(settings.output_dir if settings.output_dir.exists() else ".")
    disk_free_gb = disk.free / (1024 ** 3)

    active = sum(1 for j in job_manager.jobs.values() if j.status.value == "rendering")
    queued = sum(1 for j in job_manager.jobs.values() if j.status.value == "queued")

    return HealthResponse(
        status="ok",
        renderer_available=renderer_available,
        disk_free_gb=round(disk_free_gb, 2),
        active_jobs=active,
        queued_jobs=queued,
    )
