from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..schemas import SceneManifest, SubmitResponse, JobStatus, JobStatusResponse
from ..services.job_manager import job_manager
from ..services import registry

router = APIRouter(prefix="/renders", tags=["renders"])


@router.post("", response_model=SubmitResponse, status_code=202)
async def submit_render(manifest: SceneManifest):
    if not registry.model_exists(manifest.model.id):
        raise HTTPException(status_code=422, detail=f"Model '{manifest.model.id}' not found in registry")

    job = job_manager.submit(manifest)

    return SubmitResponse(
        job_id=job.job_id,
        status=JobStatus.queued,
        poll_url=f"/renders/{job.job_id}",
        estimate_seconds=job.estimate_seconds(),
        message="Check back in ~2 minutes.",
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_render_status(job_id: str):
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    resp = JobStatusResponse(job_id=job.job_id, status=job.status)

    if job.status == JobStatus.rendering:
        resp.progress = job.progress
        resp.estimate_seconds = job.estimate_seconds()
        pct = int(job.progress * 100)
        resp.message = f"Rendering — {pct}% complete. Check back in ~{job.estimate_seconds()}s."

    elif job.status == JobStatus.complete:
        resp.output_url = f"/renders/{job_id}/output"
        resp.log_url = f"/renders/{job_id}/log"
        resp.duration_seconds = job.duration_seconds()

    elif job.status == JobStatus.failed:
        resp.error = job.error
        resp.log_url = f"/renders/{job_id}/log" if job.log_path.exists() else None

    return resp


@router.get("/{job_id}/output")
def download_output(job_id: str):
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if job.status != JobStatus.complete:
        raise HTTPException(status_code=404, detail="Output not ready")
    if not job.output_path.exists():
        raise HTTPException(status_code=410, detail="Output has been cleaned up")
    return FileResponse(job.output_path, media_type="video/mp4", filename="output.mp4")


@router.get("/{job_id}/log")
def download_log(job_id: str):
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    if not job.log_path.exists():
        raise HTTPException(status_code=404, detail="Log not available yet")
    return FileResponse(job.log_path, media_type="text/plain", filename="render.log")
