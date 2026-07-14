"""
backend/app/api/v1/endpoints/question_bank.py
API endpoints for managing the question bank (CRUD + AI Generation + File Upload).
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel

from app.services.question_service import (
    generate_questions_for_job,
    parse_questions_from_file,
    create_manual_question,
    update_question,
    delete_question,
    list_questions,
    get_question_bank_analytics,
)
from app.db.mongo_models import JobDocument
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class GenerateQuestionsReq(BaseModel):
    job_id: str
    easy_count: int = 10
    medium_count: int = 15
    hard_count: int = 5

class ManualQuestionReq(BaseModel):
    job_id: Optional[str] = None
    skill: str
    topic: str = ""
    type: str = "mcq"
    difficulty: str = "medium"
    question_text: str
    options: List[dict] = []
    correct_answers: List[str] = []
    explanation: str = ""
    code_template: str = ""
    language: str = "python"
    test_cases: List[dict] = []
    time_limit_seconds: int = 60


@router.get("/")
async def api_list_questions(
    job_id: Optional[str] = None,
    skill: Optional[str] = None,
    difficulty: Optional[str] = None,
    q_type: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
):
    return await list_questions(job_id, skill, difficulty, q_type, limit, skip)


@router.get("/analytics")
async def api_question_analytics():
    return await get_question_bank_analytics()


@router.post("/generate")
async def api_generate_questions(req: GenerateQuestionsReq, background: BackgroundTasks):
    job = await JobDocument.get(req.job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    jd = job.description or job.requirements
    if not jd:
        raise HTTPException(400, "Job has no description/requirements for AI generation")

    background.add_task(
        generate_questions_for_job,
        job_id=req.job_id,
        job_description=jd,
        job_title=job.title,
        company=job.company,
        easy_count=req.easy_count,
        medium_count=req.medium_count,
        hard_count=req.hard_count,
    )
    return {"status": "started", "message": "AI question generation started in background."}


@router.post("/upload")
async def api_upload_questions(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    job_id: Optional[str] = Form(None),
):
    content = await file.read()
    background.add_task(
        parse_questions_from_file,
        file_content=content,
        filename=file.filename,
        job_id=job_id
    )
    return {"status": "started", "message": f"Processing {file.filename} in background."}


@router.post("/")
async def api_create_manual(req: ManualQuestionReq):
    try:
        q = await create_manual_question(req.model_dump())
        return q
    except Exception as e:
        raise HTTPException(400, str(e))


@router.put("/{question_id}")
async def api_update_question(question_id: str, req: ManualQuestionReq):
    q = await update_question(question_id, req.model_dump())
    if not q:
        raise HTTPException(404, "Not found")
    return q


@router.delete("/{question_id}")
async def api_delete_question(question_id: str):
    success = await delete_question(question_id)
    if not success:
        raise HTTPException(404, "Not found")
    return {"status": "deleted"}
