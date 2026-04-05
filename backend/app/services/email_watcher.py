import asyncio
import os
import re
import imaplib
import email as email_lib
from datetime import datetime
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Track already-processed emails by message ID to avoid double-processing
_processed_message_ids: set = set()

async def run_email_watcher():
    """
    Main entry point. Captures the MAIN loop where the DB lives 
    and passes it to the background threads.
    """
    if not settings.EMAIL_WATCHER_ENABLED:
        logger.info("[Watcher] Email watcher disabled.")
        return

    # Capture the loop that initialized the DB (Beanie/Motor)
    main_loop = asyncio.get_running_loop()
    
    logger.info(f"[Watcher] 🚀 Starting watcher for 'Important' tag: {settings.EMAIL_USER}")

    while True:
        try:
            # Pass the main_loop into the executor
            await _check_inbox_once(main_loop)
        except Exception as e:
            logger.error(f"[Watcher] Unexpected error in watcher loop: {e}")

        await asyncio.sleep(settings.EMAIL_CHECK_INTERVAL)

async def _check_inbox_once(main_loop):
    """Runs the blocking IMAP work in a thread pool, carrying the main_loop reference."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_check_inbox, main_loop)

def _sync_check_inbox(main_loop):
    """Synchronous IMAP logic running in a background thread."""
    try:
        mail = imaplib.IMAP4_SSL(settings.IMAP_SERVER)
        mail.login(settings.EMAIL_USER, settings.EMAIL_PASS)
        
        # ── Target the 'Important' Label ──────────────────────────────────────
        status, _ = mail.select('"[Gmail]/Important"')
        if status != "OK":
            logger.warning("[Watcher] '[Gmail]/Important' not found. Falling back to INBOX.")
            mail.select("INBOX")

        status, message_ids = mail.search(None, "UNSEEN")
        if status == "OK" and message_ids[0]:
            ids = message_ids[0].split()
            logger.info(f"[Watcher] Found {len(ids)} unread 'Important' email(s)")
            for num in ids:
                try:
                    _process_single_email(mail, num, main_loop)
                except Exception as e:
                    logger.error(f"[Watcher] Failed to process email {num}: {e}")
        
        mail.logout()
    except Exception as e:
        logger.error(f"[Watcher] IMAP connection error: {e}")

def _process_single_email(mail, num: bytes, main_loop):
    """Extracts attachments and triggers scoring."""
    _, data = mail.fetch(num, "(RFC822)")
    if not data or not data[0]: return

    msg = email_lib.message_from_bytes(data[0][1])
    msg_id = msg.get("Message-ID", str(num))

    if msg_id in _processed_message_ids: return

    subject = _decode_str(msg.get("Subject", "No Subject"))
    sender_name, sender_email = _parse_from(msg.get("From", ""))

    cv_paths = []
    os.makedirs(settings.SAVE_FOLDER, exist_ok=True)

    for part in msg.walk():
        if part.get_content_maintype() == "multipart": continue
        if "attachment" not in str(part.get("Content-Disposition", "")).lower(): continue

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

    if cv_paths:
        _processed_message_ids.add(msg_id)
        for cv_path in cv_paths:
            _score_and_respond(cv_path, sender_email, sender_name, main_loop)
    else:
        _processed_message_ids.add(msg_id)

def _score_and_respond(cv_path, sender_email, sender_name, main_loop):
    """Scores CV and sends emails. Bridges thread to main_loop for DB calls."""
    from app.utils.text_processing import extract_text_from_file, clean_text
    from app.agents.candidate_scorer.agent import score_candidate
    from app.integrations.email.smtp_client import SMTPClient

    # Helper to run async functions on the main loop from this thread
    def run_db_task(coro):
        future = asyncio.run_coroutine_threadsafe(coro, main_loop)
        return future.result()

    # 1. Text Extraction
    text = clean_text(extract_text_from_file(cv_path))
    if len(text) < 50: return

    # 2. Get Job (Thread-safe DB call)
    job_info = run_db_task(_get_latest_active_job())
    job_id, job_title, company, jd_text = job_info
    if not jd_text: return

    # 3. AI Scoring
    report = score_candidate(text, jd_text)
    report_dict = report.model_dump()
    report_dict.update({
        "email": sender_email,
        "candidate_name": report_dict.get("candidate_name") or sender_name
    })

    # 4. Save to DB (Thread-safe DB call)
    doc = run_db_task(_save_to_db(report_dict, job_id))
    candidate_id = str(doc.id)

    # 5. Email Response
    smtp = SMTPClient()
    decision = report_dict["final_decision"]
    
    if decision == "MATCH":
        if smtp.send_interview_invitation(
            to=sender_email, candidate_name=report_dict["candidate_name"],
            job_title=job_title, company=company, 
            match_score=report_dict["match_score"], strengths=report_dict.get("strengths", [])
        ):
            run_db_task(_mark_email_sent(candidate_id, job_id, report_dict["candidate_name"], report_dict["match_score"]))
    
    elif decision == "MAYBE":
        run_db_task(_log_maybe(candidate_id, job_id, report_dict["candidate_name"], report_dict["match_score"]))
    
    else: # NO_MATCH
        if smtp.send_rejection_email(to=sender_email, candidate_name=report_dict["candidate_name"], job_title=job_title, company=company):
            run_db_task(_mark_email_sent(candidate_id, job_id, report_dict["candidate_name"], report_dict["match_score"]))

# ── Async DB Helpers (Always called via run_coroutine_threadsafe) ─────────────

async def _get_latest_active_job():
    from app.db.mongo_models import JobDocument
    job = await JobDocument.find_one({"status": "posted"}, sort=[("created_at", -1)])
    if not job: job = await JobDocument.find_one(sort=[("created_at", -1)])
    if not job: return None, None, None, None
    return str(job.id), job.title, job.company, (job.description or job.requirements)

async def _save_to_db(report_dict, job_id):
    from app.services.mongo_service import save_candidate
    return await save_candidate(report_dict, job_id=job_id)

async def _mark_email_sent(candidate_id, job_id, name, score):
    from app.services.mongo_service import mark_email_sent, log_activity
    await mark_email_sent(candidate_id)
    await log_activity("email", f"📨 Invitation sent to {name} ({score}%)", "#3DB87A", candidate_id, job_id)

async def _log_maybe(candidate_id, job_id, name, score):
    from app.services.mongo_service import log_activity
    await log_activity("score", f"🤔 {name} ({score}%) — HR review required", "#E8A830", candidate_id, job_id)

# ── Header Helpers ────────────────────────────────────────────────────────────

def _decode_str(raw: str) -> str:
    from email.header import decode_header
    try:
        parts = decode_header(raw)
        return "".join([p[0].decode(p[1] or "utf-8") if isinstance(p[0], bytes) else str(p[0]) for p in parts])
    except: return raw

def _parse_from(from_header: str):
    m = re.search(r"<([^>]+)>", from_header)
    email_addr = m.group(1).strip() if m else from_header.strip()
    name = from_header[:from_header.index("<")].strip().strip('"') if m else email_addr.split("@")[0]
    return name, email_addr