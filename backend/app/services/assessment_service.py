"""
backend/app/services/assessment_service.py
Core business logic for the AI Interview & Assessment Module.
Handles assessment creation, session management, evaluation triggering, and reporting.
"""
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from app.core.config import settings
from app.core.logger import get_logger
from app.db.interview_models import (
    AssessmentDocument, AssessmentSessionDocument,
    QuestionDocument, EvaluationReportDocument, ViolationLogDocument
)
from app.db.mongo_models import CandidateDocument, JobDocument
from app.services.mongo_service import log_activity

logger = get_logger(__name__)


# ─── Assessment Creation ──────────────────────────────────────────────────────

async def create_assessment(
    candidate_id: str,
    job_id: str,
    resume_score: int = 0,
    question_ids: Optional[List[str]] = None,
) -> AssessmentDocument:
    """
    Create a new assessment for a shortlisted candidate.
    Generates a unique token and assessment URL.
    """
    candidate = await CandidateDocument.get(candidate_id)
    job = await JobDocument.get(job_id)

    if not candidate or not job:
        raise ValueError(f"Candidate or Job not found: {candidate_id}, {job_id}")

    if not question_ids:
        import random
        required_questions = settings.DEFAULT_QUESTION_COUNT
        
        questions = await QuestionDocument.find({"job_id": job_id}).to_list()
        
        # If the bank doesn't have a large enough pool (e.g. at least the required amount, but ideally more for variety)
        # Let's ensure we have a good pool size, say at least 25 questions, so students get unique tests.
        if len(questions) < max(required_questions, 25):
            from app.services.question_service import generate_questions_for_job
            logger.info(f"Expanding question pool for job {job.title} to ensure unique student tests...")
            await generate_questions_for_job(
                job_id=job_id,
                job_description=job.description or job.title,
                job_title=job.title,
                company=job.company,
                easy_count=10,
                medium_count=10,
                hard_count=10,
            )
            # Re-fetch after generation
            questions = await QuestionDocument.find({"job_id": job_id}).to_list()

        # Randomly sample required number of questions so each candidate gets a unique test
        if len(questions) > required_questions:
            selected_questions = random.sample(questions, required_questions)
        else:
            selected_questions = questions
            
        question_ids = [str(q.id) for q in selected_questions]

    token = str(uuid.uuid4()).replace("-", "")
    # Link directly to the frontend React app route
    assessment_url = f"{settings.ASSESSMENT_BASE_URL}/portal/{token}"
    expires_at = datetime.utcnow() + timedelta(hours=settings.ASSESSMENT_EXPIRY_HOURS)

    assessment = AssessmentDocument(
        candidate_id=candidate_id,
        job_id=job_id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        job_title=job.title,
        company=job.company,
        token=token,
        assessment_url=assessment_url,
        status="pending",
        question_ids=question_ids or [],
        duration_minutes=settings.ASSESSMENT_DURATION_MINUTES,
        total_questions=settings.DEFAULT_QUESTION_COUNT,
        easy_count=settings.DEFAULT_EASY_COUNT,
        medium_count=settings.DEFAULT_MEDIUM_COUNT,
        hard_count=settings.DEFAULT_HARD_COUNT,
        adaptive=True,
        proctoring_enabled=settings.ENABLE_PROCTORING,
        camera_enabled=settings.ENABLE_CAMERA,
        resume_score=resume_score,
        expires_at=expires_at,
    )
    await assessment.insert()

    # Update candidate record
    await candidate.set({
        "assessment_id": str(assessment.id),
        "assessment_status": "sent",
        "assessment_token": token,
        "updated_at": datetime.utcnow(),
    })

    await log_activity(
        "assessment",
        f"📋 Assessment created for <strong>{candidate.name}</strong> — {job.title}",
        color="#5B9CF6",
        candidate_id=candidate_id,
        job_id=job_id,
    )

    logger.info(f"Assessment created: {candidate.name} → {assessment_url}")
    return assessment


async def get_assessment_by_token(token: str) -> Optional[AssessmentDocument]:
    """Fetch assessment by portal token (public endpoint)."""
    return await AssessmentDocument.find_one({"token": token})


async def get_assessment_by_id(assessment_id: str) -> Optional[AssessmentDocument]:
    return await AssessmentDocument.get(assessment_id)


async def list_assessments(
    job_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[AssessmentDocument]:
    query = {}
    if job_id:
        query["job_id"] = job_id
    if status:
        query["status"] = status
    return await AssessmentDocument.find(query).sort(-AssessmentDocument.created_at).limit(limit).to_list()


# ─── Session Management ───────────────────────────────────────────────────────

async def start_session(assessment_id: str) -> AssessmentSessionDocument:
    """
    Initialize a live session when candidate clicks Start.
    Creates or resumes an existing session.
    """
    assessment = await AssessmentDocument.get(assessment_id)
    if not assessment:
        raise ValueError(f"Assessment not found: {assessment_id}")

    # Check for existing session (resume support)
    existing = await AssessmentSessionDocument.find_one({"assessment_id": assessment_id})
    if existing and existing.status == "active":
        return existing

    if existing and existing.status == "paused":
        await existing.set({"status": "active", "last_activity_at": datetime.utcnow()})
        return existing

    # Create fresh session
    duration_seconds = assessment.duration_minutes * 60
    session = AssessmentSessionDocument(
        assessment_id=assessment_id,
        candidate_id=assessment.candidate_id,
        status="active",
        current_question_idx=0,
        current_difficulty="easy",
        time_remaining_seconds=duration_seconds,
        total_duration_seconds=duration_seconds,
        started_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
    )
    await session.insert()

    # Mark assessment as active
    await assessment.set({"status": "active", "started_at": datetime.utcnow()})

    # Update candidate
    candidate = await CandidateDocument.get(assessment.candidate_id)
    if candidate:
        await candidate.set({"assessment_status": "started", "updated_at": datetime.utcnow()})

    await log_activity(
        "assessment",
        f"▶️ Assessment started by <strong>{assessment.candidate_name}</strong>",
        color="#E8A830",
        candidate_id=assessment.candidate_id,
        job_id=assessment.job_id,
    )

    return session


async def get_session(assessment_id: str) -> Optional[AssessmentSessionDocument]:
    return await AssessmentSessionDocument.find_one({"assessment_id": assessment_id})


async def submit_answer(
    session_id: str,
    question_id: str,
    answer: Any,
    time_taken_seconds: int = 0,
) -> Dict[str, Any]:
    """
    Save a single answer and update adaptive engine state.
    Returns: {is_correct, next_difficulty, progress}
    """
    session = await AssessmentSessionDocument.get(session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    question = await QuestionDocument.get(question_id)
    is_correct = False
    if question:
        is_correct = _check_answer_correctness(question, answer)

    answer_entry = {
        "question_id": question_id,
        "question_type": question.type if question else "unknown",
        "answer": answer,
        "time_taken_seconds": time_taken_seconds,
        "is_correct": is_correct,
        "skipped": answer is None,
        "answered_at": datetime.utcnow().isoformat(),
    }

    # Update session answers
    new_answers = session.answers + [answer_entry]
    correct_streak = (session.correct_streak + 1) if is_correct else 0
    wrong_streak = (session.wrong_streak + 1) if not is_correct else 0
    correct_count = session.correct_count + (1 if is_correct else 0)
    total_answered = session.total_answered + 1

    # Adaptive difficulty
    from app.agents.adaptive_engine.agent import get_next_difficulty
    next_difficulty = get_next_difficulty(
        current_difficulty=session.current_difficulty,
        correct_streak=correct_streak,
        wrong_streak=wrong_streak,
        correct_count=correct_count,
        total_answered=total_answered,
    )

    await session.set({
        "answers": new_answers,
        "current_question_idx": session.current_question_idx + 1,
        "correct_streak": correct_streak,
        "wrong_streak": wrong_streak,
        "correct_count": correct_count,
        "total_answered": total_answered,
        "current_difficulty": next_difficulty,
        "last_activity_at": datetime.utcnow(),
    })

    # Update question analytics
    if question:
        await _update_question_stats(question_id, is_correct, time_taken_seconds)

    return {
        "is_correct": is_correct,
        "next_difficulty": next_difficulty,
        "progress": total_answered,
    }


async def get_next_question(
    assessment_id: str,
    session_id: str,
) -> Optional[Dict[str, Any]]:
    """Get the next question using adaptive engine."""
    session = await AssessmentSessionDocument.get(session_id)
    assessment = await AssessmentDocument.get(assessment_id)
    if not session or not assessment:
        return None

    asked_ids = [a["question_id"] for a in session.answers]
    question_ids = assessment.question_ids

    # Get remaining questions
    remaining = [qid for qid in question_ids if qid not in asked_ids]
    if not remaining:
        return None  # All questions answered

    # Adaptive selection
    questions = []
    for qid in remaining[:20]:  # Batch fetch for performance
        q = await QuestionDocument.get(qid)
        if q:
            questions.append(q)

    if not questions:
        return None

    # Select by target difficulty
    target = session.current_difficulty
    matching = [q for q in questions if q.difficulty == target]
    if not matching:
        matching = questions  # Fallback to any

    # Pick first matching (could add weighted random selection)
    selected = matching[0]
    return _serialize_question(selected)


async def submit_assessment(assessment_id: str) -> Dict[str, Any]:
    """Final submission — marks session complete and triggers evaluation."""
    assessment = await AssessmentDocument.get(assessment_id)
    if not assessment:
        raise ValueError(f"Assessment not found: {assessment_id}")

    session = await AssessmentSessionDocument.find_one({"assessment_id": assessment_id})
    if session:
        await session.set({
            "status": "submitted",
            "submitted_at": datetime.utcnow(),
        })

    await assessment.set({
        "status": "submitted",
        "submitted_at": datetime.utcnow(),
    })

    candidate = await CandidateDocument.get(assessment.candidate_id)
    if candidate:
        await candidate.set({"assessment_status": "submitted", "updated_at": datetime.utcnow()})

    await log_activity(
        "assessment",
        f"✅ Assessment submitted by <strong>{assessment.candidate_name}</strong>",
        color="#3DB87A",
        candidate_id=assessment.candidate_id,
        job_id=assessment.job_id,
    )

    # Trigger evaluation in background
    asyncio.create_task(_run_evaluation_bg(assessment_id))

    return {"status": "submitted", "assessment_id": assessment_id}


async def auto_submit(assessment_id: str):
    """Called on timer expiry — auto-submits the session."""
    assessment = await AssessmentDocument.get(assessment_id)
    if not assessment or assessment.status in ("submitted", "evaluated"):
        return

    session = await AssessmentSessionDocument.find_one({"assessment_id": assessment_id})
    if session:
        await session.set({"status": "timed_out", "submitted_at": datetime.utcnow()})

    await assessment.set({"status": "submitted", "submitted_at": datetime.utcnow()})
    logger.info(f"Assessment auto-submitted on timeout: {assessment_id}")
    asyncio.create_task(_run_evaluation_bg(assessment_id))


# ─── Evaluation ───────────────────────────────────────────────────────────────

async def _run_evaluation_bg(assessment_id: str):
    """Background task: run AI evaluation pipeline and save report."""
    try:
        from app.agents.assessment_evaluator.agent import evaluate_assessment
        from app.services.proctoring_service import calculate_cheating_penalty_from_session

        assessment = await AssessmentDocument.get(assessment_id)
        if not assessment:
            return

        session = await AssessmentSessionDocument.find_one({"assessment_id": assessment_id})
        if not session:
            return

        # Collect question documents
        questions = []
        for qid in assessment.question_ids:
            q = await QuestionDocument.get(qid)
            if q:
                questions.append(q.model_dump(mode="json"))

        session_data = session.model_dump(mode="json")

        # Calculate cheating penalty
        cheating_penalty = calculate_cheating_penalty_from_session(session_data)

        # Run evaluation pipeline
        report_dict = evaluate_assessment(
            candidate_id=assessment.candidate_id,
            job_id=assessment.job_id,
            assessment_id=assessment_id,
            resume_score=assessment.resume_score,
            session_data=session_data,
            questions=questions,
            cheating_penalty=cheating_penalty,
        )

        # Save evaluation report
        report_doc = EvaluationReportDocument(
            candidate_id=assessment.candidate_id,
            job_id=assessment.job_id,
            assessment_id=assessment_id,
            **{k: v for k, v in report_dict.items() if k not in ("candidate_id", "job_id", "assessment_id")},
        )
        await report_doc.insert()

        # Update assessment with scores
        await assessment.set({
            "status": "evaluated",
            "mcq_score": report_dict.get("mcq_score", 0),
            "coding_score": report_dict.get("coding_score", 0),
            "short_answer_score": report_dict.get("short_answer_score", 0),
            "communication_score": report_dict.get("communication_score", 0),
            "problem_solving_score": report_dict.get("problem_solving_score", 0),
            "cheating_penalty": cheating_penalty,
            "final_composite_score": report_dict.get("final_composite_score", 0),
            "evaluated_at": datetime.utcnow(),
        })

        # Update candidate record
        candidate = await CandidateDocument.get(assessment.candidate_id)
        if candidate:
            await candidate.set({
                "assessment_status": "evaluated",
                "assessment_score": report_dict.get("final_composite_score", 0),
                "final_composite_score": report_dict.get("final_composite_score", 0),
                "assessment_report_id": str(report_doc.id),
                "updated_at": datetime.utcnow(),
            })

        await log_activity(
            "assessment",
            f"🤖 AI evaluation complete for <strong>{assessment.candidate_name}</strong> "
            f"— Final Score: {report_dict.get('final_composite_score', 0):.1f}%",
            color="#C8A96E",
            candidate_id=assessment.candidate_id,
            job_id=assessment.job_id,
        )

        # Send report email to HR
        from app.integrations.email.smtp_client import SMTPClient
        smtp = SMTPClient()
        smtp.send_assessment_report_to_hr(
            to=settings.INTERVIEWER_EMAIL,
            candidate_name=assessment.candidate_name,
            job_title=assessment.job_title,
            company=assessment.company,
            final_score=report_dict.get("final_composite_score", 0),
            recommendation=report_dict.get("recommendation", "reject"),
            report_summary=report_dict.get("candidate_summary", ""),
        )

        # Send conditional notification to candidate based on final score
        final_score = report_dict.get("final_composite_score", 0)
        if final_score >= 80:
            smtp.send_assessment_passed_email(
                to=assessment.candidate_email,
                candidate_name=assessment.candidate_name,
                job_title=assessment.job_title,
                company=assessment.company,
                score=final_score,
            )
        else:
            smtp.send_assessment_failed_email(
                to=assessment.candidate_email,
                candidate_name=assessment.candidate_name,
                job_title=assessment.job_title,
                company=assessment.company,
                score=final_score,
                strengths=report_dict.get("strengths", []),
                weaknesses=report_dict.get("weaknesses", []),
            )

        logger.info(f"Evaluation complete: {assessment.candidate_name} → {report_dict.get('final_composite_score', 0):.1f}%")

    except Exception as e:
        logger.error(f"Evaluation failed for {assessment_id}: {e}", exc_info=True)


async def get_evaluation_report(assessment_id: str) -> Optional[Dict[str, Any]]:
    """Get the evaluation report for an assessment."""
    report = await EvaluationReportDocument.find_one({"assessment_id": assessment_id})
    if not report:
        return None
    return report.model_dump(mode="json")


# ─── Dashboard Data ───────────────────────────────────────────────────────────

async def get_assessment_dashboard_stats() -> Dict[str, Any]:
    """Get assessment analytics for HR dashboard."""
    total = await AssessmentDocument.count()
    pending = await AssessmentDocument.find({"status": "pending"}).count()
    active = await AssessmentDocument.find({"status": "active"}).count()
    submitted = await AssessmentDocument.find({"status": "submitted"}).count()
    evaluated = await AssessmentDocument.find({"status": "evaluated"}).count()
    expired = await AssessmentDocument.find({"status": "expired"}).count()
    completed = submitted + evaluated

    # Score distribution
    all_assessed = await AssessmentDocument.find({"status": "evaluated"}).to_list()
    scores = [a.final_composite_score for a in all_assessed if a.final_composite_score > 0]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    pass_count = sum(1 for s in scores if s >= 60)
    pass_rate = round(pass_count / len(scores) * 100, 1) if scores else 0

    # Fetch all assessments for the table
    all_docs = await AssessmentDocument.find().sort(-AssessmentDocument.created_at).limit(100).to_list()

    # Fetch violation counts for all sessions
    from app.db.interview_models import AssessmentSessionDocument
    assessments_list = []
    for a in all_docs:
        # Get session info
        session = await AssessmentSessionDocument.find_one({"assessment_id": str(a.id)})
        violation_count = session.total_violations if session else 0
        time_taken = None
        if a.started_at and a.submitted_at:
            time_taken = int((a.submitted_at - a.started_at).total_seconds() // 60)

        # Get recommendation from evaluation report
        recommendation = None
        if a.status == "evaluated":
            report = await EvaluationReportDocument.find_one({"assessment_id": str(a.id)})
            if report:
                recommendation = report.recommendation

        assessments_list.append({
            "id": str(a.id),
            "candidate_name": a.candidate_name,
            "candidate_email": a.candidate_email,
            "job_title": a.job_title,
            "company": a.company,
            "status": a.status,
            "final_score": round(a.final_composite_score, 1) if a.final_composite_score else None,
            "mcq_score": round(a.mcq_score, 1) if a.mcq_score else None,
            "coding_score": round(a.coding_score, 1) if a.coding_score else None,
            "short_answer_score": round(a.short_answer_score, 1) if a.short_answer_score else None,
            "cheating_penalty": a.cheating_penalty,
            "total_questions": a.total_questions,
            "violation_count": violation_count,
            "recommendation": recommendation,
            "time_taken_minutes": time_taken,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        })

    return {
        "total": total,
        "pending": pending,
        "active": active,
        "in_progress": active,
        "submitted": submitted,
        "evaluated": evaluated,
        "completed": completed,
        "expired": expired,
        "avg_score": avg_score,
        "pass_rate": pass_rate,
        "pass_count": pass_count,
        "score_distribution": _bucket_scores(scores),
        "assessments": assessments_list,
    }


async def get_live_assessments() -> List[Dict[str, Any]]:
    """Get currently active assessment sessions for HR live view."""
    sessions = await AssessmentSessionDocument.find({"status": "active"}).to_list()
    result = []
    for s in sessions:
        assessment = await AssessmentDocument.get(s.assessment_id)
        if assessment:
            result.append({
                "session_id": str(s.id),
                "assessment_id": s.assessment_id,
                "candidate_name": assessment.candidate_name,
                "job_title": assessment.job_title,
                "progress": f"{s.total_answered}/{assessment.total_questions}",
                "time_remaining": s.time_remaining_seconds,
                "current_difficulty": s.current_difficulty,
                "violations": s.total_violations,
                "started_at": s.started_at.isoformat() if s.started_at else None,
            })
    return result


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _check_answer_correctness(question: QuestionDocument, answer: Any) -> bool:
    """Deterministically check if an answer is correct for auto-graded types."""
    if question.type in ("mcq", "true_false"):
        # correct_answers stores option ids like ["a"] or ["a", "c"]
        correct_ids = [str(c).lower() for c in question.correct_answers]
        options = question.options  # [{"id": "a", "text": "..."}, ...] or ["str", ...]

        def _resolve_to_ids(ans_val) -> list:
            """Map any answer representation to a list of option-id strings."""
            if ans_val is None:
                return []
            if isinstance(ans_val, list):
                result = []
                for item in ans_val:
                    result.extend(_resolve_to_ids(item))
                return result
            if isinstance(ans_val, int):
                # Numeric index → resolve to option id
                if 0 <= ans_val < len(options):
                    opt = options[ans_val]
                    if isinstance(opt, dict):
                        return [str(opt.get("id", ans_val)).lower()]
                    return [str(opt).lower()]
                return [str(ans_val).lower()]
            # String: could be option id, uppercase letter (A→a), or full option text
            val = str(ans_val).strip()
            candidates = [val.lower()]
            # Also resolve full-text matches to id
            for opt in options:
                if isinstance(opt, dict):
                    opt_text = str(opt.get("text", "") or opt.get("label", "")).strip().lower()
                    opt_id   = str(opt.get("id",   "") or opt.get("value", "")).strip().lower()
                    if val.lower() == opt_text and opt_id:
                        candidates.append(opt_id)
            return candidates

        resolved = _resolve_to_ids(answer)
        if isinstance(answer, list):
            return set(resolved) == set(correct_ids)
        return bool(set(resolved) & set(correct_ids))

    elif question.type == "fill_blank":
        if isinstance(answer, str):
            return answer.strip().lower() == question.blank_answer.strip().lower()
    return False  # Non-auto-graded types return False (evaluated by AI)


def _serialize_question(q: QuestionDocument) -> Dict[str, Any]:
    """Serialize a question for the frontend (remove correct answers)."""
    return {
        "id": str(q.id),
        "type": q.type,
        "difficulty": q.difficulty,
        "question_text": q.question_text,
        "options": q.options,
        "code_template": q.code_template,
        "language": q.language,
        "time_limit_seconds": q.time_limit_seconds,
        "skill": q.skill,
        "topic": q.topic,
        # NOTE: correct_answers NOT included — never exposed to frontend
    }


def _bucket_scores(scores: List[float]) -> List[int]:
    """Bucket scores into distribution: 0-20, 20-40, 40-60, 60-80, 80-100."""
    buckets = [0] * 5
    for s in scores:
        if s < 20:      buckets[0] += 1
        elif s < 40:    buckets[1] += 1
        elif s < 60:    buckets[2] += 1
        elif s < 80:    buckets[3] += 1
        else:           buckets[4] += 1
    return buckets


async def _update_question_stats(question_id: str, is_correct: bool, time_taken: int):
    """Update analytics on a question after it's answered."""
    q = await QuestionDocument.get(question_id)
    if not q:
        return
    new_used = q.times_used + 1
    new_correct = q.times_correct + (1 if is_correct else 0)
    new_pass_rate = round(new_correct / new_used, 3)
    # Rolling average for time
    new_avg_time = round((q.avg_time_seconds * q.times_used + time_taken) / new_used, 1)
    await q.set({
        "times_used": new_used,
        "times_correct": new_correct,
        "pass_rate": new_pass_rate,
        "avg_time_seconds": new_avg_time,
        "too_easy": new_pass_rate > 0.9,
        "too_hard": new_pass_rate < 0.1,
        "updated_at": datetime.utcnow(),
    })

async def delete_assessment(assessment_id: str) -> bool:
    """Delete an assessment and its associated sessions, violations, and reports."""
    assessment = await AssessmentDocument.get(assessment_id)
    if not assessment:
        return False
        
    sessions = await AssessmentSessionDocument.find({"assessment_id": assessment_id}).to_list()
    for s in sessions:
        await s.delete()
        
    violations = await ViolationLogDocument.find({"assessment_id": assessment_id}).to_list()
    for v in violations:
        await v.delete()
        
    reports = await EvaluationReportDocument.find({"assessment_id": assessment_id}).to_list()
    for r in reports:
        await r.delete()
        
    await assessment.delete()
    return True
