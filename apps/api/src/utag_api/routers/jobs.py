from uuid import UUID

from fastapi import APIRouter

from utag_api.dependencies import CurrentPrincipal, DbSession
from utag_api.errors import ApiError
from utag_api.models import BackgroundJob
from utag_api.schemas.domain import BackgroundJobView

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=BackgroundJobView)
async def get_job(
    job_id: UUID,
    db: DbSession,
    principal: CurrentPrincipal,
) -> BackgroundJobView:
    job = await db.get(BackgroundJob, job_id)
    if job is None:
        raise ApiError(404, "job_not_found", "Job not found")
    is_owner = job.owner_id == principal.user.id
    can_manage = "jobs.manage" in principal.permissions
    if not is_owner and not can_manage:
        raise ApiError(404, "job_not_found", "Job not found")
    return BackgroundJobView.model_validate(job)
