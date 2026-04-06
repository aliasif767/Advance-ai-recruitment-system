"""
backend/app/api/v1/endpoints/jobs.py
Fixed: posts full detailed JD to LinkedIn, not a short one-liner.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from app.services.mongo_service import create_job, get_job, list_jobs, update_job, mark_job_posted, log_activity
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class CreateJobRequest(BaseModel):
    title: str
    company: str
    requirements: str
    location: str = "Remote"
    employment_type: str = "Full-time"
    experience_years: int = 0
    salary_range: str = ""
    auto_generate_jd: bool = True
    auto_post_linkedin: bool = False


class UpdateJobRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    required_skills: Optional[List[str]] = None


@router.post("/")
async def create_job_endpoint(req: CreateJobRequest, background: BackgroundTasks):
    """Create a job, auto-generate a full JD with AI, optionally post to LinkedIn."""
    try:
        job_data = req.model_dump(exclude={"auto_generate_jd", "auto_post_linkedin"})
        job_data["status"] = "draft"
        job_data["description"] = req.requirements
        job_data["short_description"] = ""

        if req.auto_generate_jd:
            try:
                from app.agents.jd_generator.agent import JDGeneratorAgent
                from app.models.schemas import JobRequirements
                logger.info(f"Generating JD for: {req.title} @ {req.company}")
                agent = JDGeneratorAgent()
                jd = agent.generate(JobRequirements(
                    job_title=req.title,
                    company_name=req.company,
                    key_requirements=req.requirements,
                    location=req.location,
                    experience_years=req.experience_years,
                    salary_range=req.salary_range,
                    employment_type=req.employment_type,
                ))
                job_data["description"]       = jd.job_description
                job_data["short_description"] = jd.short_description
                job_data["required_skills"]   = jd.required_skills
                job_data["nice_to_have"]      = jd.nice_to_have
                logger.info(f"JD generated. LinkedIn post length: {len(jd.short_description)} chars")
            except Exception as e:
                logger.error(f"JD generation failed: {e}")
                # Fallback: build a decent description manually instead of one-liner
                job_data["description"] = f"""
# {req.title} at {req.company}

## About the Role
We are looking for a talented {req.title} to join {req.company}.

## Requirements
{req.requirements}

## Details
- Location: {req.location}
- Type: {req.employment_type}
- Experience: {req.experience_years}+ years
- Salary: {req.salary_range or 'Competitive'}

## How to Apply
Send your CV to our recruitment email with subject: "Application - {req.title}"
""".strip()
                job_data["short_description"] = (
                    f"🚀 We're Hiring: {req.title} at {req.company}!\n\n"
                    f"📍 {req.location} | 💼 {req.employment_type} | ⏰ {req.experience_years}+ yrs\n\n"
                    f"🔧 Requirements: {req.requirements[:300]}\n\n"
                    f"💰 Salary: {req.salary_range or 'Competitive'}\n\n"
                    f"📩 Send your CV to our recruitment email.\n"
                    f"Subject: 'Application - {req.title}'\n\n"
                    f"#Hiring #NowHiring #{req.title.replace(' ','')} #{req.company.replace(' ','')}"
                )

        job = await create_job(job_data)

        # Post to LinkedIn using the FULL detailed short_description (not job_data["short_description"])
        if req.auto_post_linkedin:
            background.add_task(
                _post_linkedin_bg,
                str(job.id),
                job_data["short_description"],   # this is the full rich LinkedIn post
            )

        return _serialize_job(job)

    except Exception as e:
        logger.error(f"Create job error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_jobs_endpoint(status: Optional[str] = None):
    jobs = await list_jobs(status)
    return [_serialize_job(j) for j in jobs]


@router.get("/{job_id}")
async def get_job_endpoint(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _serialize_job(job)


@router.patch("/{job_id}")
async def update_job_endpoint(job_id: str, req: UpdateJobRequest):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    job = await update_job(job_id, data)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _serialize_job(job)


@router.post("/{job_id}/post-linkedin")
async def post_to_linkedin(job_id: str):
    """Post the full detailed JD to LinkedIn."""
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        from app.integrations.linkedin.linkedin_api import LinkedInClient
        client = LinkedInClient()
        # Use short_description (the rich LinkedIn post) — fall back to full description
        post_text = job.short_description or job.description
        # LinkedIn UGC posts support up to 3000 chars
        post_text = post_text[:3000]
        logger.info(f"Posting to LinkedIn: {len(post_text)} chars")
        result = client.post_job(post_text)
        if result["success"]:
            await mark_job_posted(job_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _post_linkedin_bg(job_id: str, text: str):
    try:
        from app.integrations.linkedin.linkedin_api import LinkedInClient
        client = LinkedInClient()
        result = client.post_job(text[:3000])
        if result["success"]:
            await mark_job_posted(job_id)
            logger.info(f"LinkedIn post successful for job {job_id}")
        else:
            logger.error(f"LinkedIn post failed: {result['message']}")
    except Exception as e:
        logger.error(f"LinkedIn background post exception: {e}")


def _serialize_job(j) -> dict:
    return {
        "id": str(j.id),
        "title": j.title,
        "company": j.company,
        "description": j.description,
        "short_description": j.short_description,
        "requirements": j.requirements,
        "location": j.location,
        "employment_type": j.employment_type,
        "experience_years": j.experience_years,
        "salary_range": j.salary_range,
        "required_skills": j.required_skills,
        "nice_to_have": j.nice_to_have,
        "status": j.status,
        "linkedin_posted": j.linkedin_posted,
        "created_at": j.created_at.isoformat(),
    }