"""
backend/app/api/v1/endpoints/pipeline.py

Key feature: /pipeline/watch-inbox
- Connects to 2020n07689@gmail.com
- Reads ALL unread emails with CV attachments
- Scores each CV against a specified job using LangGraph AI
- Automatically sends interview invitation to MATCH candidates
- Automatically sends rejection to NO_MATCH candidates
- Saves everything to MongoDB
"""
import os
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.services.mongo_service import (
    start_pipeline_run, complete_pipeline_run,
    list_pipeline_runs, save_candidate, get_job, log_activity
)
from app.core.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class WatchInboxRequest(BaseModel):
    job_id: str
    send_emails: bool = True          # auto-send interview/rejection emails
    match_threshold: int = 70         # score >= this → MATCH → interview email
    maybe_threshold: int = 50         # score >= this → MAYBE (HR reviews manually)


class PipelineRunRequest(BaseModel):
    job_id: str
    cv_folder: str = "received_cvs"
    send_emails: bool = True


class ScoreOnlyRequest(BaseModel):
    cv_folder: str
    job_description: str
    job_id: Optional[str] = None


# ── MAIN: Watch inbox and auto-process CVs ────────────────────────────────────

@router.post("/watch-inbox")
async def watch_inbox(req: WatchInboxRequest, background: BackgroundTasks):
    """
    Watch email inbox → extract CVs → score with AI → auto-send emails.
    Runs in background so API returns immediately.
    """
    job = await get_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    run = await start_pipeline_run(
        job_id=req.job_id,
        job_title=job.title,
        company=job.company,
    )

    background.add_task(
        _watch_inbox_bg,
        run.run_id,
        req.job_id,
        job.description or job.requirements,
        job.title,
        job.company,
        req.send_emails,
        req.match_threshold,
        req.maybe_threshold,
    )

    return {
        "run_id": run.run_id,
        "status": "started",
        "message": f"Watching inbox for CVs... Job: {job.title}",
        "email_account": "configured in .env (EMAIL_USER)",
        "auto_email": req.send_emails,
    }


@router.post("/run")
async def run_pipeline(req: PipelineRunRequest, background: BackgroundTasks):
    """Score all CVs in a local folder against a job."""
    job = await get_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    run = await start_pipeline_run(
        job_id=req.job_id, job_title=job.title, company=job.company
    )

    background.add_task(
        _run_folder_bg,
        run.run_id, req.job_id,
        job.description or job.requirements,
        job.title, job.company,
        req.cv_folder, req.send_emails,
    )

    return {"run_id": run.run_id, "status": "started", "message": f"Pipeline started for {job.title}"}


@router.post("/score-only")
async def score_only(req: ScoreOnlyRequest):
    """Score all CVs in a folder synchronously (no email sending)."""
    try:
        from app.agents.resume_parser.agent import ResumeParserAgent
        from app.agents.candidate_scorer.agent import score_candidate
        parser = ResumeParserAgent()
        parsed = parser.parse_folder(req.cv_folder)
        results = []
        for cv_path, text in parsed:
            try:
                report = score_candidate(text, req.job_description)
                rd = report.model_dump()
                rd["cv_filename"] = os.path.basename(cv_path)
                doc = await save_candidate(rd, job_id=req.job_id)
                results.append({"id": str(doc.id), "name": doc.name, "score": doc.match_score, "decision": doc.final_decision})
            except Exception as e:
                results.append({"error": str(e), "cv": cv_path})
        return {"processed": len(parsed), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs")
async def list_runs(limit: int = 20):
    runs = await list_pipeline_runs(limit=limit)
    return [_serialize_run(r) for r in runs]


# ── BACKGROUND TASKS ──────────────────────────────────────────────────────────

async def _watch_inbox_bg(
    run_id: str,
    job_id: str,
    jd_text: str,
    job_title: str,
    company: str,
    send_emails: bool,
    match_threshold: int,
    maybe_threshold: int,
):
    """
    Full automated pipeline:
    1. Connect to inbox via IMAP
    2. Download all unread CV attachments
    3. Parse text from each CV
    4. Score each CV with LangGraph AI
    5. Save results to MongoDB
    6. Send interview email if MATCH, rejection if NO_MATCH
    """
    from app.integrations.email.imap_client import IMAPClient
    from app.agents.resume_parser.agent import ResumeParserAgent
    from app.agents.candidate_scorer.agent import score_candidate
    from app.integrations.email.smtp_client import SMTPClient

    matches, maybes, no_matches, errors = [], [], [], []
    emails_sent = 0

    try:
        logger.info(f"[Pipeline {run_id}] Starting inbox watch for job: {job_title}")

        # Step 1: Fetch CVs from inbox
        imap = IMAPClient()
        applications = imap.fetch_applications()

        if not applications:
            logger.info(f"[Pipeline {run_id}] No new CV emails found in inbox.")
            await complete_pipeline_run(run_id, {
                "total_cvs_processed": 0, "matches": [], "maybes": [],
                "no_matches": [], "emails_sent": 0, "errors": ["No new CV emails found."],
            })
            return

        logger.info(f"[Pipeline {run_id}] Found {len(applications)} CV email(s). Processing...")

        parser = ResumeParserAgent()
        smtp   = SMTPClient()

        for app in applications:
            for cv_path in app.cv_paths:
                try:
                    # Step 2: Parse CV text
                    text = parser.parse_file(cv_path)
                    if len(text) < 30:
                        errors.append(f"Could not extract text from {os.path.basename(cv_path)}")
                        continue

                    # Step 3: Score with AI
                    logger.info(f"[Pipeline {run_id}] Scoring: {os.path.basename(cv_path)} from {app.sender_email}")
                    report = score_candidate(text, jd_text)

                    # Override email with the actual sender's email (from inbox)
                    report_dict = report.model_dump()
                    report_dict["cv_filename"] = os.path.basename(cv_path)

                    # Always use the real sender email from inbox
                    if app.sender_email:
                        report_dict["email"] = app.sender_email
                    if app.sender_name and report_dict.get("candidate_name") in ("Unknown", "Candidate", ""):
                        report_dict["candidate_name"] = app.sender_name

                    # Step 4: Save to MongoDB
                    doc = await save_candidate(report_dict, job_id=job_id)
                    candidate_name = doc.name
                    candidate_email = doc.email
                    score = doc.match_score

                    logger.info(f"[Pipeline {run_id}] {candidate_name}: {score}% → {doc.final_decision}")

                    if doc.final_decision == "MATCH":
                        matches.append({"id": str(doc.id), "name": candidate_name, "score": score})
                    elif doc.final_decision == "MAYBE":
                        maybes.append({"id": str(doc.id), "name": candidate_name, "score": score})
                    else:
                        no_matches.append({"id": str(doc.id), "name": candidate_name, "score": score})

                    # Step 5: Send email automatically
                    if send_emails and candidate_email:
                        if doc.final_decision == "MATCH":
                            logger.info(f"[Pipeline {run_id}] Sending interview invitation to {candidate_email}")
                            sent = smtp.send_interview_invitation(
                                to=candidate_email,
                                candidate_name=candidate_name,
                                job_title=job_title,
                                company=company,
                                match_score=score,
                                strengths=doc.strengths,
                            )
                            if sent:
                                emails_sent += 1
                                from app.services.mongo_service import mark_email_sent
                                await mark_email_sent(str(doc.id))
                                await log_activity(
                                    "email",
                                    f"✅ Interview invitation sent to <strong>{candidate_name}</strong> ({score}%)",
                                    color="#3DB87A",
                                    candidate_id=str(doc.id),
                                    job_id=job_id,
                                )

                        elif doc.final_decision == "NO_MATCH":
                            logger.info(f"[Pipeline {run_id}] Sending rejection to {candidate_email}")
                            sent = smtp.send_rejection_email(
                                to=candidate_email,
                                candidate_name=candidate_name,
                                job_title=job_title,
                                company=company,
                            )
                            if sent:
                                emails_sent += 1
                                from app.services.mongo_service import mark_email_sent
                                await mark_email_sent(str(doc.id))

                    elif doc.final_decision in ("MATCH", "MAYBE") and not candidate_email:
                        logger.warning(f"[Pipeline {run_id}] No email found for {candidate_name} — cannot send invitation")

                except Exception as e:
                    err_msg = f"Failed to process {os.path.basename(cv_path)}: {e}"
                    logger.error(f"[Pipeline {run_id}] {err_msg}")
                    errors.append(err_msg)

        total = len(matches) + len(maybes) + len(no_matches)
        logger.info(
            f"[Pipeline {run_id}] Complete — "
            f"MATCH:{len(matches)} MAYBE:{len(maybes)} NO_MATCH:{len(no_matches)} "
            f"Emails:{emails_sent}"
        )

        await complete_pipeline_run(run_id, {
            "total_cvs_processed": total,
            "matches": matches,
            "maybes": maybes,
            "no_matches": no_matches,
            "emails_sent": emails_sent,
            "errors": errors,
        })

    except Exception as e:
        logger.error(f"[Pipeline {run_id}] Fatal error: {e}")
        await complete_pipeline_run(run_id, {
            "total_cvs_processed": 0, "matches": [], "maybes": [],
            "no_matches": [], "emails_sent": 0, "errors": [str(e)],
        })


async def _run_folder_bg(
    run_id: str, job_id: str, jd_text: str,
    job_title: str, company: str,
    cv_folder: str, send_emails: bool,
):
    """Score CVs from a local folder (no inbox check)."""
    from app.agents.resume_parser.agent import ResumeParserAgent
    from app.agents.candidate_scorer.agent import score_candidate
    from app.integrations.email.smtp_client import SMTPClient

    matches, maybes, no_matches, errors = [], [], [], []
    emails_sent = 0

    try:
        parser = ResumeParserAgent()
        smtp   = SMTPClient()
        parsed = parser.parse_folder(cv_folder)

        for cv_path, text in parsed:
            try:
                report = score_candidate(text, jd_text)
                rd = report.model_dump()
                rd["cv_filename"] = os.path.basename(cv_path)
                doc = await save_candidate(rd, job_id=job_id)

                if doc.final_decision == "MATCH":
                    matches.append({"id": str(doc.id)})
                    if send_emails and doc.email:
                        sent = smtp.send_interview_invitation(
                            to=doc.email, candidate_name=doc.name,
                            job_title=job_title, company=company,
                            match_score=doc.match_score, strengths=doc.strengths,
                        )
                        if sent:
                            emails_sent += 1
                            from app.services.mongo_service import mark_email_sent
                            await mark_email_sent(str(doc.id))
                elif doc.final_decision == "MAYBE":
                    maybes.append({"id": str(doc.id)})
                else:
                    no_matches.append({"id": str(doc.id)})
                    if send_emails and doc.email:
                        smtp.send_rejection_email(
                            to=doc.email, candidate_name=doc.name,
                            job_title=job_title, company=company,
                        )
                        emails_sent += 1
            except Exception as e:
                errors.append(str(e))

        await complete_pipeline_run(run_id, {
            "total_cvs_processed": len(parsed),
            "matches": matches, "maybes": maybes,
            "no_matches": no_matches,
            "emails_sent": emails_sent, "errors": errors,
        })
    except Exception as e:
        await complete_pipeline_run(run_id, {
            "total_cvs_processed": 0, "matches": [], "maybes": [],
            "no_matches": [], "emails_sent": 0, "errors": [str(e)],
        })


def _serialize_run(r) -> dict:
    return {
        "id": str(r.id), "run_id": r.run_id, "job_id": r.job_id,
        "job_title": r.job_title, "company": r.company, "status": r.status,
        "total_cvs": r.total_cvs, "matched": r.matched, "maybe": r.maybe,
        "no_match": r.no_match, "emails_sent": r.emails_sent, "errors": r.errors,
        "started_at": r.started_at.isoformat(),
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "duration_seconds": r.duration_seconds,
    }