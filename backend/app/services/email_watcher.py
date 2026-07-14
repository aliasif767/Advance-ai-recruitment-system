import asyncio
import os
import re
import imaplib
import email as email_lib
from datetime import datetime
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_processed_message_ids: set = set()


async def run_email_watcher():
    if not settings.EMAIL_WATCHER_ENABLED:
        logger.info("[Watcher] Email watcher disabled.")
        return

    main_loop = asyncio.get_running_loop()
    logger.info(f"[Watcher] Starting watcher: {settings.EMAIL_USER}")

    while True:
        try:
            await _check_inbox_once(main_loop)
        except Exception as e:
            logger.error(f"[Watcher] Unexpected error: {e}")
        await asyncio.sleep(settings.EMAIL_CHECK_INTERVAL)


async def _check_inbox_once(main_loop):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_check_inbox, main_loop)


def _sync_check_inbox(main_loop):
    try:
        mail = imaplib.IMAP4_SSL(settings.IMAP_SERVER)
        mail.login(settings.EMAIL_USER, settings.EMAIL_PASS)

        status, _ = mail.select("INBOX")
        if status != "OK":
            logger.error("[Watcher] INBOX not found.")
            mail.logout()
            return

        status, message_ids = mail.search(None, 'X-GM-RAW', '"category:primary is:unread newer_than:2d"')
        if status == "OK" and message_ids[0]:
            ids = message_ids[0].split()
            logger.info(f"[Watcher] Found {len(ids)} unread email(s)")
            for num in ids:
                try:
                    _process_single_email(mail, num, main_loop)
                except Exception as e:
                    logger.error(f"[Watcher] Failed to process email {num}: {e}")

        mail.logout()
    except Exception as e:
        logger.error(f"[Watcher] IMAP connection error: {e}")


def _process_single_email(mail, num: bytes, main_loop):
    _, data = mail.fetch(num, "(RFC822)")
    if not data or not data[0]:
        return

    msg = email_lib.message_from_bytes(data[0][1])
    msg_id = msg.get("Message-ID", str(num))

    if msg_id in _processed_message_ids:
        return

    subject = _decode_str(msg.get("Subject", "No Subject"))
    sender_name, sender_email = _parse_from(msg.get("From", ""))

    logger.info(f"[Watcher] Email from {sender_email} | Subject: {subject}")

    cv_paths = []
    os.makedirs(settings.SAVE_FOLDER, exist_ok=True)

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if "attachment" not in str(part.get("Content-Disposition", "")).lower():
            continue

        filename = _decode_str(part.get_filename() or "cv.pdf")
        _, ext = os.path.splitext(filename.lower())

        if ext in {".pdf", ".docx", ".txt"}:
            safe_prefix = re.sub(r"[^\w]", "_", sender_email.split("@")[0])[:20]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_name = f"{safe_prefix}_{timestamp}_{filename}"
            filepath = os.path.join(settings.SAVE_FOLDER, final_name)

            with open(filepath, "wb") as f:
                f.write(part.get_payload(decode=True))
            cv_paths.append(filepath)

    _processed_message_ids.add(msg_id)

    if cv_paths:
        for cv_path in cv_paths:
            _route_and_score(cv_path, sender_email, sender_name, subject, main_loop)
    else:
        logger.info(f"[Watcher] No CV attachments from {sender_email}, skipping.")


def _route_and_score(cv_path, sender_email, sender_name, subject, main_loop):
    """
    1. Parse email subject or CV text → detect which job the candidate applied for.
    2. Check hiring_active on that job.
    3. If closed → send professional position-filled email.
    4. If open   → score CV against that specific job's JD.
    """
    from app.integrations.email.smtp_client import SMTPClient
    from app.utils.text_processing import extract_text_from_file, clean_text

    def run_db_task(coro):
        future = asyncio.run_coroutine_threadsafe(coro, main_loop)
        return future.result()

    smtp = SMTPClient()

    text = clean_text(extract_text_from_file(cv_path))
    if len(text) < 50:
        logger.warning(f"[Watcher] CV text too short from {sender_email}, skipping.")
        return

    # Step 1: Resolve job from subject or CV text
    job_id, job_title, company, jd_text, hiring_active = run_db_task(
        _resolve_job(subject, text)
    )

    if not job_id:
        logger.warning(f"[Watcher] Could not match '{subject}' or CV to any job. Sending no-role rejection to {sender_email}.")
        smtp.send_no_role_rejection_email(to=sender_email, candidate_name=sender_name)
        return

    logger.info(f"[Watcher] Routed {sender_email} → '{job_title}' (hiring_active={hiring_active})")

    # Step 2: Check hiring gate
    if not hiring_active:
        logger.info(f"[Watcher] Hiring closed for '{job_title}'. Sending position-filled email to {sender_email}.")
        smtp.send_position_filled_email(
            to=sender_email,
            candidate_name=sender_name,
            job_title=job_title,
            company=company,
        )
        run_db_task(_log_position_filled(sender_email, job_title, job_id))
        return

    # Step 3: Score and respond
    _score_and_respond(text, sender_email, sender_name, job_id, job_title, company, jd_text, main_loop)


def _score_and_respond(text, sender_email, sender_name, job_id, job_title, company, jd_text, main_loop):
    from app.agents.candidate_scorer.agent import score_candidate
    from app.integrations.email.smtp_client import SMTPClient
    from app.core.config import settings
    from app.services.assessment_service import create_assessment

    def run_db_task(coro):
        future = asyncio.run_coroutine_threadsafe(coro, main_loop)
        return future.result()

    report = score_candidate(text, jd_text)
    report_dict = report.model_dump()
    report_dict.update({
        "email": sender_email,
        "candidate_name": report_dict.get("candidate_name") or sender_name,
        "applied_role": job_title,
    })

    doc = run_db_task(_save_to_db(report_dict, job_id))
    candidate_id = str(doc.id)

    smtp = SMTPClient()
    decision = report_dict["final_decision"]

    if decision == "MATCH":
        if settings.AUTO_SEND_ASSESSMENT:
            logger.info(f"[Watcher] Auto-sending assessment to {sender_email}")
            try:
                assessment = run_db_task(create_assessment(
                    candidate_id=candidate_id,
                    job_id=job_id,
                    resume_score=report_dict["match_score"]
                ))
                if smtp.send_assessment_invitation(
                    to=sender_email,
                    candidate_name=report_dict["candidate_name"],
                    job_title=job_title,
                    company=company,
                    assessment_url=assessment.assessment_url,
                    duration_minutes=assessment.duration_minutes
                ):
                    run_db_task(_mark_assessment_sent(candidate_id, job_id, report_dict["candidate_name"], report_dict["match_score"]))
            except Exception as e:
                logger.error(f"[Watcher] Failed to create assessment: {e}")
        else:
            if smtp.send_interview_invitation(
                to=sender_email,
                candidate_name=report_dict["candidate_name"],
                job_title=job_title,
                company=company,
                match_score=report_dict["match_score"],
                strengths=report_dict.get("strengths", []),
            ):
                run_db_task(_mark_email_sent(candidate_id, job_id, report_dict["candidate_name"], report_dict["match_score"]))

    elif decision == "MAYBE":
        run_db_task(_log_maybe(candidate_id, job_id, report_dict["candidate_name"], report_dict["match_score"]))

    else:
        if smtp.send_rejection_email(
            to=sender_email,
            candidate_name=report_dict["candidate_name"],
            job_title=job_title,
            company=company,
        ):
            run_db_task(_mark_email_sent(candidate_id, job_id, report_dict["candidate_name"], report_dict["match_score"]))


# ── Async DB Helpers ──────────────────────────────────────────────────────────

async def _resolve_job(subject: str, cv_text: str):
    """
    Parse email subject to find which job the candidate applied for.
    If the subject is vague, use an LLM to analyze the CV text and pick the best matching active job.

    Supported patterns (case-insensitive):
      "Application for AI Engineer"
      "Applying for Fullstack Developer"
      "Apply - Senior Backend Dev"
      "Job Application: Data Scientist"
      "Re: AI Engineer Position"

    Returns: (job_id, job_title, company, jd_text, hiring_active)
    """
    from app.db.mongo_models import JobDocument

    all_jobs = await JobDocument.find().sort(-JobDocument.created_at).to_list()
    if not all_jobs:
        return None, None, None, None, False

    role_phrase = _extract_role_from_subject(subject)
    logger.info(f"[Watcher] Role phrase from subject: '{role_phrase}'")

    if role_phrase:
        best_job = None
        best_score = 0
        role_lower = role_phrase.lower()
        role_tokens = set(re.sub(r"[^\w\s]", "", role_lower).split())

        for job in all_jobs:
            title_lower = job.title.lower()
            title_tokens = set(re.sub(r"[^\w\s]", "", title_lower).split())
            if not title_tokens:
                continue

            overlap = len(role_tokens & title_tokens)
            similarity = overlap / max(len(role_tokens), len(title_tokens))

            # Bonus for substring match
            if role_lower in title_lower or title_lower in role_lower:
                similarity += 0.4

            if similarity > best_score:
                best_score = similarity
                best_job = job

        if best_job and best_score >= 0.2:
            logger.info(f"[Watcher] Matched to '{best_job.title}' (score={best_score:.2f})")
            return (
                str(best_job.id),
                best_job.title,
                best_job.company,
                best_job.description or best_job.requirements,
                best_job.hiring_active,
            )

    # Fallback: CV-based Routing via LLM
    logger.info(f"[Watcher] No strong subject match for '{subject}'. Falling back to CV-based LLM routing.")
    active_jobs = [j for j in all_jobs if j.status == "posted"]
    if active_jobs:
        from app.agents.candidate_scorer.agent import route_cv_to_job
        best_job_id = route_cv_to_job(cv_text, active_jobs)
        if best_job_id:
            for job in active_jobs:
                if str(job.id) == best_job_id:
                    logger.info(f"[Watcher] LLM Routed CV to: '{job.title}'")
                    return (
                        str(job.id),
                        job.title,
                        job.company,
                        job.description or job.requirements,
                        job.hiring_active,
                    )
    
    logger.info(f"[Watcher] LLM Routing failed or no jobs active. Returning None.")
    return None, None, None, None, False


def _extract_role_from_subject(subject: str) -> str:
    """Extract the role/position name from common application email subject lines."""
    subject = subject.strip()

    pattern = (
        r"(?:application\s+for|applying\s+for|apply\s+for|apply\s*[-\u2013:]\s*|"
        r"job\s+application[:\s]+|position\s+of\s+|re:\s*)"
        r"(.+?)(?:\s+(?:position|role|job))?$"
    )
    m = re.search(pattern, subject, re.IGNORECASE)
    if m:
        extracted = m.group(1).strip().rstrip(".,;!?")
        extracted = re.sub(r"\s+at\s+\S+.*$", "", extracted, flags=re.IGNORECASE).strip()
        if len(extracted) > 2:
            return extracted

    # Short subject: strip prefixes and use directly
    if len(subject) < 60:
        cleaned = re.sub(r"^(re:|fw:|fwd:)\s*", "", subject, flags=re.IGNORECASE).strip()
        return cleaned

    return ""


async def _save_to_db(report_dict, job_id):
    from app.services.mongo_service import save_candidate
    return await save_candidate(report_dict, job_id=job_id)


async def _mark_email_sent(candidate_id, job_id, name, score):
    from app.services.mongo_service import mark_email_sent, log_activity
    await mark_email_sent(candidate_id)
    await log_activity("email", f"📨 Email sent to {name} ({score}%)", "#3DB87A", candidate_id, job_id)

async def _mark_assessment_sent(candidate_id, job_id, name, score):
    from app.services.mongo_service import mark_email_sent, log_activity
    await mark_email_sent(candidate_id)
    await log_activity("email", f"📨 Assessment invitation sent to {name} ({score}%)", "#9B59B6", candidate_id, job_id)


async def _log_maybe(candidate_id, job_id, name, score):
    from app.services.mongo_service import log_activity
    await log_activity("score", f"🤔 {name} ({score}%) — HR review required", "#E8A830", candidate_id, job_id)


async def _log_position_filled(sender_email, job_title, job_id):
    from app.services.mongo_service import log_activity
    await log_activity(
        "email",
        f"📭 Position-filled email sent to {sender_email} (applied for: {job_title})",
        "#5A5A62",
        job_id=job_id,
    )


# ── Header Helpers ────────────────────────────────────────────────────────────

def _decode_str(raw: str) -> str:
    from email.header import decode_header
    try:
        parts = decode_header(raw)
        return "".join(
            [p[0].decode(p[1] or "utf-8") if isinstance(p[0], bytes) else str(p[0]) for p in parts]
        )
    except:
        return raw


def _parse_from(from_header: str):
    m = re.search(r"<([^>]+)>", from_header)
    email_addr = m.group(1).strip() if m else from_header.strip()
    name = from_header[:from_header.index("<")].strip().strip('"') if m else email_addr.split("@")[0]
    return name, email_addr