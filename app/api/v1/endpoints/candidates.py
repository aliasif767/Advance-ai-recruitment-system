"""
backend/app/api/v1/endpoints/candidates.py
GET    /candidates/             List candidates (filterable)
GET    /candidates/{id}         Get candidate detail
POST   /candidates/score/file   Upload CV + score against a job
POST   /candidates/score/text   Score raw text
PATCH  /candidates/{id}         Update decision / notes
DELETE /candidates/{id}         Delete candidate
POST   /candidates/{id}/send-email   Send outreach/rejection email
"""
import os
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from typing import Optional

from app.services.mongo_service import (
    save_candidate, get_candidate, list_candidates,
    mark_email_sent, mark_interview_scheduled, delete_candidate, log_activity
)
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

SUPPORTED = {".pdf", ".docx", ".txt"}


class ScoreTextRequest(BaseModel):
    resume_text: str
    job_description: str
    job_id: Optional[str] = None


class UpdateCandidateRequest(BaseModel):
    final_decision: Optional[str] = None
    interview_slot: Optional[str] = None
    notes: Optional[str] = None


@router.get("/")
async def list_candidates_endpoint(
    decision: Optional[str] = Query(None),
    job_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    skip: int = Query(0),
):
    docs = await list_candidates(decision=decision, job_id=job_id, limit=limit, skip=skip)
    return [_serialize(d) for d in docs]


@router.get("/{candidate_id}")
async def get_candidate_endpoint(candidate_id: str):
    doc = await get_candidate(candidate_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return _serialize(doc)


@router.post("/score/file")
async def score_from_file(
    file: UploadFile = File(...),
    job_id: str = Form(...),
):
    """Upload a CV file, score it against the job, save to MongoDB."""
    _, ext = os.path.splitext(file.filename or "")
    if ext.lower() not in SUPPORTED:
        raise HTTPException(status_code=422, detail=f"Unsupported format: {ext}. Use PDF/DOCX/TXT")

    try:
        from app.db.mongo_models import JobDocument
        job = await JobDocument.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Save temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # Parse CV text
        from app.utils.text_processing import extract_text_from_file, clean_text
        raw = extract_text_from_file(tmp_path)
        text = clean_text(raw)
        os.unlink(tmp_path)

        if len(text) < 50:
            raise HTTPException(status_code=422, detail="Could not extract text from CV. Try a text-based PDF.")

        # Score using LangGraph pipeline
        from app.agents.candidate_scorer.agent import score_candidate
        report = score_candidate(text, job.description or job.requirements)
        report_dict = report.model_dump()
        report_dict["cv_filename"] = file.filename

        # Save to MongoDB
        doc = await save_candidate(report_dict, job_id=job_id)
        return _serialize(doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Score file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/score/text")
async def score_from_text(req: ScoreTextRequest):
    """Score raw resume text against a job description."""
    try:
        from app.agents.candidate_scorer.agent import score_candidate
        report = score_candidate(req.resume_text, req.job_description)
        report_dict = report.model_dump()
        doc = await save_candidate(report_dict, job_id=req.job_id)
        return _serialize(doc)
    except Exception as e:
        logger.error(f"Score text error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{candidate_id}")
async def update_candidate(candidate_id: str, req: UpdateCandidateRequest):
    doc = await get_candidate(candidate_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Candidate not found")

    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    if req.interview_slot:
        await mark_interview_scheduled(candidate_id, req.interview_slot)
    elif update_data:
        from datetime import datetime
        update_data["updated_at"] = datetime.utcnow()
        await doc.set(update_data)

    return _serialize(await get_candidate(candidate_id))


@router.delete("/{candidate_id}")
async def delete_candidate_endpoint(candidate_id: str):
    ok = await delete_candidate(candidate_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"deleted": True}


@router.post("/{candidate_id}/send-email")
async def send_email_endpoint(candidate_id: str):
    """Send the AI-drafted outreach or rejection email."""
    doc = await get_candidate(candidate_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not doc.email:
        raise HTTPException(status_code=422, detail="Candidate has no email address")

    try:
        from app.integrations.email.smtp_client import SMTPClient
        smtp = SMTPClient()
        if doc.final_decision in ("MATCH", "MAYBE") and doc.outreach_email_draft:
            body = doc.outreach_email_draft
            subject = f"Interview Invitation — {doc.name}"
        else:
            body = doc.rejection_email_draft or f"Dear {doc.name},\n\nThank you for your application. We will be in touch.\n\nBest,\nRecruitment Team"
            subject = f"Your Application Update — {doc.name}"

        ok = smtp.send(to=doc.email, subject=subject, body=body)
        if ok:
            await mark_email_sent(candidate_id)
            return {"sent": True, "to": doc.email}
        raise HTTPException(status_code=500, detail="SMTP send failed")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _serialize(d) -> dict:
    return {
        "id": str(d.id),
        "name": d.name,
        "email": d.email,
        "phone": d.phone,
        "university": d.university,
        "cgpa": d.cgpa,
        "github_handle": d.github_handle,
        "years_of_experience": d.years_of_experience,
        "cv_filename": d.cv_filename,
        "match_score": d.match_score,
        "final_decision": d.final_decision,
        "job_id": d.job_id,
        "job_title": d.job_title,
        "skill_matches": d.skill_matches,
        "language_matches": d.language_matches,
        "project_highlights": d.project_highlights,
        "evaluation_scores": d.evaluation_scores,
        "strengths": d.strengths,
        "red_flags": d.red_flags,
        "cultural_fit_notes": d.cultural_fit_notes,
        "github_summary": d.github_summary,
        "outreach_email_draft": d.outreach_email_draft,
        "rejection_email_draft": d.rejection_email_draft,
        "email_sent": d.email_sent,
        "email_sent_at": d.email_sent_at.isoformat() if d.email_sent_at else None,
        "interview_scheduled": d.interview_scheduled,
        "interview_slot": d.interview_slot,
        "created_at": d.created_at.isoformat(),
    }
