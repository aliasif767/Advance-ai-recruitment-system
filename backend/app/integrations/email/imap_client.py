import imaplib
import email
import os
import re
from email.header import decode_header
from dataclasses import dataclass, field
from typing import List, Optional
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}

@dataclass
class IngestedApplication:
    sender_email: str
    sender_name: str
    subject: str
    body_text: str
    cv_paths: List[str] = field(default_factory=list)

class IMAPClient:
    """
    Connects to Gmail and downloads unread emails flagged as 'Important' 
    that contain PDF/DOCX/TXT attachments.
    """

    def __init__(self):
        self.user   = settings.EMAIL_USER
        self.pwd    = settings.EMAIL_PASS
        self.host   = settings.IMAP_SERVER
        self.folder = settings.SAVE_FOLDER
        os.makedirs(self.folder, exist_ok=True)

    def fetch_applications(self, mailbox: str = '"[Gmail]/Important"') -> List[IngestedApplication]:
        """
        Connects to IMAP, focuses on 'Important' emails, finds UNSEEN messages,
        and returns IngestedApplication objects.
        """
        results: List[IngestedApplication] = []

        try:
            logger.info(f"Connecting to {self.host} (Folder: {mailbox}) as {self.user}...")
            mail = imaplib.IMAP4_SSL(self.host)
            mail.login(self.user, self.pwd)
            
            # Select the Important mailbox
            status, _ = mail.select(mailbox)
            
            if status != "OK":
                logger.warning(f"Mailbox {mailbox} not found. Falling back to INBOX.")
                mail.select("INBOX")

            # Search ONLY unread emails within the Important tag
            status, messages = mail.search(None, "UNSEEN")
            if status != "OK" or not messages[0]:
                logger.info("No unread 'Important' emails found.")
                mail.logout()
                return results

            email_ids = messages[0].split()
            logger.info(f"Found {len(email_ids)} unread 'Important' email(s) to process.")

            for num in email_ids:
                try:
                    app = self._process_message(mail, num)
                    if app:
                        results.append(app)
                        logger.info(f"✅ CV received: {app.sender_email}")
                except Exception as e:
                    logger.error(f"Failed to process email {num}: {e}")

            mail.logout()

        except Exception as e:
            logger.error(f"IMAP error: {e}")

        return results

    def _process_message(self, mail: imaplib.IMAP4_SSL, num: bytes) -> Optional[IngestedApplication]:
        """Parse one email — extract sender, subject, body, and CV attachments."""
        _, data = mail.fetch(num, "(RFC822)")
        if not data or not data[0]:
            return None

        msg = email.message_from_bytes(data[0][1])

        subject     = self._decode_header_value(msg.get("Subject", "No Subject"))
        from_header = self._decode_header_value(msg.get("From", ""))
        sender_name, sender_email = self._parse_from(from_header)
        body_text   = self._extract_body(msg)

        cv_paths: List[str] = []
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" not in disposition.lower():
                continue

            filename = self._decode_header_value(part.get_filename() or "")
            _, ext = os.path.splitext(filename.lower())

            if ext in SUPPORTED_EXTENSIONS:
                safe_sender = re.sub(r"[^\w]", "_", sender_email.split("@")[0])[:20]
                safe_name   = re.sub(r"[^\w.\-]", "_", filename)
                final_name  = f"{safe_sender}_{safe_name}"
                filepath    = os.path.join(self.folder, final_name)

                with open(filepath, "wb") as f:
                    f.write(part.get_payload(decode=True))

                cv_paths.append(filepath)

        if not cv_paths:
            return None

        return IngestedApplication(
            sender_email=sender_email,
            sender_name=sender_name,
            subject=subject,
            body_text=body_text,
            cv_paths=cv_paths,
        )

    @staticmethod
    def _decode_header_value(raw: str) -> str:
        try:
            parts = decode_header(raw)
            decoded = []
            for part, enc in parts:
                if isinstance(part, bytes):
                    decoded.append(part.decode(enc or "utf-8", errors="ignore"))
                else:
                    decoded.append(str(part))
            return " ".join(decoded).strip()
        except: return raw or ""

    @staticmethod
    def _parse_from(from_header: str):
        m = re.search(r"<([^>]+)>", from_header)
        email_addr = m.group(1).strip() if m else from_header.strip()
        name = from_header[:from_header.index("<")].strip().strip('"') if m else email_addr.split("@")[0]
        return name, email_addr

    @staticmethod
    def _extract_body(msg) -> str:
        body = ""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        p = part.get_payload(decode=True)
                        if p: body = p.decode("utf-8", errors="ignore")
                        break
            else:
                p = msg.get_payload(decode=True)
                if p: body = p.decode("utf-8", errors="ignore")
        except: pass
        return body.strip()