"""
backend/app/api/v1/endpoints/assessments.py
API endpoints for managing and taking assessments.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.services.assessment_service import (
    create_assessment,
    get_assessment_by_id,
    get_assessment_by_token,
    list_assessments,
    start_session,
    get_session,
    submit_answer,
    get_next_question,
    submit_assessment,
    get_evaluation_report,
    get_assessment_dashboard_stats,
    get_live_assessments,
)
from app.services.proctoring_service import log_violation, get_violation_summary
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class CreateAssessmentReq(BaseModel):
    candidate_id: str
    job_id: str
    resume_score: int = 0
    question_ids: Optional[List[str]] = None

class AnswerReq(BaseModel):
    question_id: str
    answer: Any
    time_taken_seconds: int = 0

class ProctoringEventReq(BaseModel):
    candidate_id: str
    violation_type: str
    description: str = ""
    screenshot_b64: Optional[str] = None
    metadata: dict = {}


# ─── HR Endpoints ─────────────────────────────────────────────────────────────

@router.post("/create")
async def api_create_assessment(req: CreateAssessmentReq):
    try:
        assessment = await create_assessment(
            req.candidate_id, req.job_id, req.resume_score, req.question_ids
        )
        return {"assessment_id": str(assessment.id), "url": assessment.assessment_url}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard")
async def api_dashboard_stats():
    return await get_assessment_dashboard_stats()

@router.get("/live")
async def api_live_assessments():
    return await get_live_assessments()

@router.get("/{assessment_id}")
async def api_get_assessment(assessment_id: str):
    assessment = await get_assessment_by_id(assessment_id)
    if not assessment:
        raise HTTPException(404, "Not found")
    return assessment

@router.get("/{assessment_id}/report")
async def api_get_report(assessment_id: str):
    report = await get_evaluation_report(assessment_id)
    if not report:
        raise HTTPException(404, "Report not ready or not found")
    return report

@router.get("/{assessment_id}/violations")
async def api_get_violations(assessment_id: str):
    session = await get_session(assessment_id)
    if not session:
        return {"total_violations": 0}
    return await get_violation_summary(str(session.id))


# ─── Candidate Portal Endpoints ───────────────────────────────────────────────

@router.get("/portal/{token}")
async def api_portal_init(token: str):
    """Initial load for the assessment portal."""
    assessment = await get_assessment_by_token(token)
    if not assessment:
        raise HTTPException(404, "Invalid or expired assessment link")
    
    return {
        "assessment_id": str(assessment.id),
        "candidate_name": assessment.candidate_name,
        "job_title": assessment.job_title,
        "company": assessment.company,
        "status": assessment.status,
        "duration_minutes": assessment.duration_minutes,
        "total_questions": assessment.total_questions,
        "proctoring_enabled": assessment.proctoring_enabled,
        "camera_enabled": assessment.camera_enabled,
    }

@router.post("/{assessment_id}/start")
async def api_start_session(assessment_id: str):
    try:
        session = await start_session(assessment_id)
        return {
            "session_id": str(session.id),
            "time_remaining_seconds": session.time_remaining_seconds,
            "status": session.status
        }
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.get("/{assessment_id}/session/{session_id}/next")
async def api_next_question(assessment_id: str, session_id: str):
    question = await get_next_question(assessment_id, session_id)
    if not question:
        return {"complete": True}
    return {"complete": False, "question": question}

@router.post("/{assessment_id}/session/{session_id}/answer")
async def api_submit_answer(assessment_id: str, session_id: str, req: AnswerReq):
    try:
        res = await submit_answer(session_id, req.question_id, req.answer, req.time_taken_seconds)
        return res
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{assessment_id}/submit")
async def api_submit_assessment(assessment_id: str):
    try:
        return await submit_assessment(assessment_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/{assessment_id}/session/{session_id}/violation")
async def api_log_violation(assessment_id: str, session_id: str, req: ProctoringEventReq):
    await log_violation(
        session_id=session_id,
        assessment_id=assessment_id,
        candidate_id=req.candidate_id,
        violation_type=req.violation_type,
        description=req.description,
        screenshot_b64=req.screenshot_b64,
        metadata=req.metadata,
    )
    return {"status": "logged"}

@router.delete("/{assessment_id}")
async def delete_assessment_endpoint(assessment_id: str):
    from app.services.assessment_service import delete_assessment
    success = await delete_assessment(assessment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {"status": "success", "message": "Assessment deleted successfully"}
