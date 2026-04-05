"""
backend/app/integrations/email/smtp_client.py
Sends rich HTML interview invitation and rejection emails.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class SMTPClient:

    def send(self, to: str, subject: str, body: str, html: bool = False) -> bool:
        """Send a plain text or HTML email."""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"]    = f"IARS Recruitment <{settings.EMAIL_USER}>"
            msg["To"]      = to
            msg["Subject"] = subject

            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type, "utf-8"))

            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as s:
                s.ehlo()
                s.starttls()
                s.login(settings.EMAIL_USER, settings.EMAIL_PASS)
                s.sendmail(settings.EMAIL_USER, to, msg.as_string())

            logger.info(f"✅ Email sent → {to} | {subject}")
            return True

        except Exception as e:
            logger.error(f"❌ SMTP failed → {to}: {e}")
            return False

    def send_interview_invitation(
        self,
        to: str,
        candidate_name: str,
        job_title: str,
        company: str,
        match_score: int,
        strengths: list,
    ) -> bool:
        """Send a professional HTML interview invitation email."""

        strengths_html = "".join(f"<li>{s}</li>" for s in strengths[:3]) if strengths else "<li>Strong technical background</li>"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
    .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); padding: 40px 32px; text-align: center; }}
    .header h1 {{ color: #C8A96E; font-size: 28px; margin: 0 0 8px; font-weight: 700; }}
    .header p {{ color: #9B9A94; font-size: 14px; margin: 0; }}
    .score-badge {{ display: inline-block; background: #3DB87A; color: white; font-size: 22px; font-weight: bold; padding: 12px 24px; border-radius: 50px; margin: 16px 0; }}
    .body {{ padding: 32px; }}
    .body h2 {{ color: #1a1a2e; font-size: 22px; margin-bottom: 8px; }}
    .body p {{ color: #555; line-height: 1.7; font-size: 15px; }}
    .strengths {{ background: #f0faf5; border-left: 4px solid #3DB87A; border-radius: 0 8px 8px 0; padding: 16px 20px; margin: 20px 0; }}
    .strengths h3 {{ color: #3DB87A; margin: 0 0 10px; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; }}
    .strengths ul {{ margin: 0; padding-left: 20px; color: #333; }}
    .strengths li {{ margin-bottom: 6px; font-size: 14px; }}
    .cta {{ background: #C8A96E; color: #1a1a2e; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: bold; font-size: 16px; display: inline-block; margin: 20px 0; }}
    .next-steps {{ background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0; }}
    .next-steps h3 {{ color: #1a1a2e; margin: 0 0 12px; font-size: 16px; }}
    .step {{ display: flex; align-items: flex-start; margin-bottom: 10px; }}
    .step-num {{ background: #C8A96E; color: #1a1a2e; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; flex-shrink: 0; margin-right: 12px; margin-top: 2px; }}
    .footer {{ background: #1a1a2e; padding: 24px 32px; text-align: center; }}
    .footer p {{ color: #5A5A62; font-size: 12px; margin: 4px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🎉 Congratulations!</h1>
      <p>You have been shortlisted for an interview</p>
      <div class="score-badge">Match Score: {match_score}%</div>
    </div>

    <div class="body">
      <h2>Dear {candidate_name},</h2>
      <p>
        We are thrilled to inform you that after carefully reviewing your CV and profile,
        you have been <strong>shortlisted for the position of {job_title}</strong> at <strong>{company}</strong>.
      </p>
      <p>
        Your profile stood out from a competitive pool of candidates, and we believe your
        skills and experience align excellently with what we are looking for.
      </p>

      <div class="strengths">
        <h3>✅ Why You Stood Out</h3>
        <ul>
          {strengths_html}
        </ul>
      </div>

      <div class="next-steps">
        <h3>📋 Next Steps</h3>
        <div class="step">
          <div class="step-num">1</div>
          <div><strong>Reply to this email</strong> with your availability for the coming week (preferred time slots)</div>
        </div>
        <div class="step">
          <div class="step-num">2</div>
          <div><strong>Prepare your portfolio</strong> — bring examples of relevant projects or GitHub links</div>
        </div>
        <div class="step">
          <div class="step-num">3</div>
          <div><strong>Interview format</strong> — 45-minute technical + cultural fit discussion (video call)</div>
        </div>
      </div>

      <p>
        Please reply to this email within <strong>48 hours</strong> to confirm your interest
        and share your availability. We look forward to speaking with you!
      </p>

      <p>
        If you have any questions, feel free to reply directly to this email.
      </p>

      <p>
        Warm regards,<br>
        <strong>Recruitment Team</strong><br>
        {company}
      </p>
    </div>

    <div class="footer">
      <p>This email was sent by the IARS Automated Recruitment System</p>
      <p>{company} · Recruitment Department</p>
    </div>
  </div>
</body>
</html>
"""
        return self.send(
            to=to,
            subject=f"🎉 Interview Invitation — {job_title} at {company}",
            body=html_body,
            html=True,
        )

    def send_rejection_email(
        self,
        to: str,
        candidate_name: str,
        job_title: str,
        company: str,
    ) -> bool:
        """Send a respectful rejection email."""
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
    .header {{ background: #1a1a2e; padding: 32px; text-align: center; }}
    .header h1 {{ color: #9B9A94; font-size: 22px; margin: 0; }}
    .body {{ padding: 32px; }}
    .body p {{ color: #555; line-height: 1.7; font-size: 15px; }}
    .footer {{ background: #1a1a2e; padding: 20px 32px; text-align: center; }}
    .footer p {{ color: #5A5A62; font-size: 12px; margin: 4px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>Application Update — {job_title}</h1></div>
    <div class="body">
      <p>Dear {candidate_name},</p>
      <p>
        Thank you sincerely for taking the time to apply for the <strong>{job_title}</strong>
        position at <strong>{company}</strong> and for your interest in joining our team.
      </p>
      <p>
        After carefully reviewing your profile, we have decided to move forward with other
        candidates whose experience more closely matches our current requirements for this specific role.
      </p>
      <p>
        This was not an easy decision — we received many strong applications. We encourage you
        to keep building your skills and apply again for future openings that match your profile.
      </p>
      <p>
        We wish you the very best in your career journey and hope our paths cross again in the future.
      </p>
      <p>
        Kind regards,<br>
        <strong>Recruitment Team</strong><br>
        {company}
      </p>
    </div>
    <div class="footer">
      <p>This email was sent by the IARS Automated Recruitment System</p>
      <p>{company} · Recruitment Department</p>
    </div>
  </div>
</body>
</html>
"""
        return self.send(
            to=to,
            subject=f"Your Application for {job_title} at {company}",
            body=html_body,
            html=True,
        )