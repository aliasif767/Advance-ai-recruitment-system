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

    def send_assessment_invitation(
        self,
        to: str,
        candidate_name: str,
        job_title: str,
        company: str,
        assessment_url: str,
        duration_minutes: int,
    ) -> bool:
        """Send an HTML assessment invitation email with secure token link."""
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
    .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #6a1b9a 100%); padding: 40px 32px; text-align: center; }}
    .header h1 {{ color: #ffffff; font-size: 28px; margin: 0 0 8px; font-weight: 700; }}
    .header p {{ color: #e0e0e0; font-size: 15px; margin: 0; }}
    .body {{ padding: 32px; }}
    .body h2 {{ color: #1a1a2e; font-size: 22px; margin-bottom: 8px; }}
    .body p {{ color: #555; line-height: 1.7; font-size: 15px; }}
    .details-box {{ background: #f3f0f5; border-left: 4px solid #9B59B6; border-radius: 0 8px 8px 0; padding: 20px; margin: 24px 0; }}
    .details-box p {{ margin: 8px 0; font-weight: 500; color: #333; }}
    .cta-container {{ text-align: center; margin: 32px 0; }}
    .cta {{ background: #9B59B6; color: #ffffff; text-decoration: none; padding: 16px 36px; border-radius: 8px; font-weight: bold; font-size: 18px; display: inline-block; transition: background 0.3s; }}
    .cta:hover {{ background: #8e44ad; }}
    .footer {{ background: #1a1a2e; padding: 24px 32px; text-align: center; }}
    .footer p {{ color: #5A5A62; font-size: 12px; margin: 4px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Assessment Invitation</h1>
      <p>{job_title} · {company}</p>
    </div>
    <div class="body">
      <h2>Hello {candidate_name},</h2>
      <p>
        Congratulations! Your profile has been shortlisted for the <strong>{job_title}</strong> position at <strong>{company}</strong>.
        As the next step in our recruitment process, we invite you to complete a technical assessment.
      </p>
      
      <div class="details-box">
        <p>⏱️ <strong>Duration:</strong> {duration_minutes} Minutes</p>
        <p>📷 <strong>Format:</strong> Adaptive Questions & Coding</p>
        <p>⏳ <strong>Expires in:</strong> 72 Hours</p>
      </div>

      <p>
        This assessment is designed to evaluate your technical skills and problem-solving abilities.
        Ensure you are in a quiet environment with a stable internet connection before starting.
      </p>

      <div class="cta-container">
        <a href="{assessment_url}" class="cta">Start Assessment</a>
      </div>

      <p>Best of luck!<br><strong>The {company} Team</strong></p>
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
            subject=f"Action Required: Assessment for {job_title} at {company}",
            body=html_body,
            html=True,
        )

    def send_assessment_submitted_confirmation(
        self,
        to: str,
        candidate_name: str,
        job_title: str,
        company: str,
    ) -> bool:
        """Send confirmation that the assessment was successfully submitted."""
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
    .header {{ background: #3DB87A; padding: 32px; text-align: center; }}
    .header h1 {{ color: #ffffff; font-size: 22px; margin: 0; }}
    .body {{ padding: 32px; }}
    .body p {{ color: #555; line-height: 1.7; font-size: 15px; }}
    .footer {{ background: #1a1a2e; padding: 20px 32px; text-align: center; }}
    .footer p {{ color: #5A5A62; font-size: 12px; margin: 4px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header"><h1>Assessment Received</h1></div>
    <div class="body">
      <p>Hi {candidate_name},</p>
      <p>
        Thank you for completing the technical assessment for the <strong>{job_title}</strong> role at <strong>{company}</strong>.
        Your submission has been successfully received by our system.
      </p>
      <p>
        Our AI evaluation engine is currently reviewing your answers. We will get back to you with the results and next steps very soon.
      </p>
      <p>Regards,<br><strong>The {company} Team</strong></p>
    </div>
    <div class="footer">
      <p>This email was sent by the IARS Automated Recruitment System</p>
    </div>
  </div>
</body>
</html>
"""
        return self.send(
            to=to,
            subject=f"Assessment Received — {job_title} at {company}",
            body=html_body,
            html=True,
        )

    def send_assessment_report_to_hr(
        self,
        to: str,
        candidate_name: str,
        job_title: str,
        company: str,
        final_score: float,
        recommendation: str,
        report_summary: str,
    ) -> bool:
        """Send the evaluation summary report directly to the HR/Interviewer email."""
        color = "#3DB87A" if final_score >= 70 else "#E8A830" if final_score >= 50 else "#E05555"
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
    .header {{ background: #1a1a2e; padding: 24px; text-align: center; }}
    .header h1 {{ color: #ffffff; font-size: 20px; margin: 0; }}
    .score-badge {{ display: inline-block; background: {color}; color: white; padding: 12px 24px; border-radius: 50px; font-size: 24px; font-weight: bold; margin: 20px 0; }}
    .body {{ padding: 32px; }}
    .body p {{ color: #555; line-height: 1.6; font-size: 15px; }}
    .summary-box {{ background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 20px 0; border: 1px solid #ddd; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>IARS Assessment Report</h1>
    </div>
    <div class="body" style="text-align: center;">
      <p><strong>{candidate_name}</strong> has completed the assessment for <strong>{job_title}</strong>.</p>
      <div class="score-badge">{final_score:.1f}%</div>
      <p style="text-transform: uppercase; font-weight: bold; color: {color};">{recommendation.replace('_', ' ')}</p>
      
      <div class="summary-box" style="text-align: left;">
        <p><strong>AI Summary:</strong><br>{report_summary}</p>
      </div>
      
      <p>Log in to the IARS Dashboard to view the full detailed report, breakdown of answers, and proctoring logs.</p>
    </div>
  </div>
</body>
</html>
"""
        return self.send(
            to=to,
            subject=f"[IARS Report] {candidate_name} — {final_score:.1f}% ({job_title})",
            body=html_body,
            html=True,
        )

    def send_position_filled_email(
        self,
        to: str,
        candidate_name: str,
        job_title: str,
        company: str,
    ) -> bool:
        """
        Send a professional 'position has been filled' email when hiring_active=False.
        Encourages the candidate to watch for future openings.
        """
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
    .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 32px; text-align: center; }}
    .header h1 {{ color: #C8A96E; font-size: 20px; margin: 0; font-weight: 600; }}
    .header p {{ color: #9B9A94; font-size: 13px; margin: 8px 0 0; }}
    .body {{ padding: 36px 32px; }}
    .body p {{ color: #444; line-height: 1.75; font-size: 15px; margin-bottom: 16px; }}
    .notice-box {{ background: #f8f8f2; border-left: 4px solid #C8A96E; border-radius: 0 8px 8px 0; padding: 16px 20px; margin: 24px 0; }}
    .notice-box p {{ margin: 0; color: #555; font-size: 14px; }}
    .footer {{ background: #1a1a2e; padding: 22px 32px; text-align: center; }}
    .footer p {{ color: #5A5A62; font-size: 12px; margin: 4px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Thank You for Your Interest</h1>
      <p>{job_title} · {company}</p>
    </div>
    <div class="body">
      <p>Dear {candidate_name},</p>
      <p>
        Thank you sincerely for taking the time to apply for the
        <strong>{job_title}</strong> position at <strong>{company}</strong>.
        We truly appreciate your interest in joining our team.
      </p>
      <div class="notice-box">
        <p>
          We regret to inform you that the <strong>{job_title}</strong> position
          has already been filled. We are no longer accepting applications for
          this specific role at this time.
        </p>
      </div>
      <p>
        Your profile and qualifications are impressive, and we would love to
        keep you in mind for future opportunities. We encourage you to watch
        our LinkedIn page and official channels for upcoming openings that
        may align with your skills and experience.
      </p>
      <p>
        Please do not hesitate to apply again when a suitable role becomes
        available — we would be delighted to hear from you.
      </p>
      <p>
        We wish you every success in your job search and future career endeavours.
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
            subject=f"Re: Your Application for {job_title} at {company}",
            body=html_body,
            html=True,
        )

    def send_no_role_rejection_email(self, to: str, candidate_name: str) -> bool:
        """Send a respectful rejection when no open roles match the CV."""
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
    <div class="header"><h1>Application Update</h1></div>
    <div class="body">
      <p>Dear {candidate_name},</p>
      <p>
        Thank you sincerely for sending your CV to us and expressing interest in joining our team.
      </p>
      <p>
        After reviewing your profile, we could not find any current open positions that strongly match your specific skill set and experience level. 
      </p>
      <p>
        We encourage you to monitor our career page and apply directly for future openings that match your profile.
      </p>
      <p>
        We wish you the very best in your career journey and hope our paths cross again.
      </p>
      <p>
        Kind regards,<br>
        <strong>Recruitment Team</strong><br>
        IARS Recruitment
      </p>
    </div>
    <div class="footer">
      <p>This email was sent by the IARS Automated Recruitment System</p>
    </div>
  </div>
</body>
</html>
"""
        return self.send(
            to=to,
            subject=f"Update on your application to IARS",
            body=html_body,
            html=True,
        )

    def send_assessment_passed_email(
        self,
        to: str,
        candidate_name: str,
        job_title: str,
        company: str,
        score: float,
    ) -> bool:
        """Send a physical interview invitation for scoring >= 80%."""
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
      <p>Assessment Completed Successfully</p>
      <div class="score-badge">Assessment Score: {score:.1f}%</div>
    </div>

    <div class="body">
      <h2>Dear {candidate_name},</h2>
      <p>
        We are thrilled to inform you that you have cleared the technical assessment stage for the 
        <strong>{job_title}</strong> position at <strong>{company}</strong> with an outstanding score of <strong>{score:.1f}%</strong>!
      </p>
      <p>
        Your performance has met our high standards, and we would like to invite you for a 
        <strong>physical interview with the Technical Manager of the company</strong>.
      </p>

      <div class="next-steps">
        <h3>📋 What's Next?</h3>
        <div class="step">
          <div class="step-num">1</div>
          <div><strong>Schedule Interview:</strong> A member of our HR team will contact you shortly to coordinate a suitable date and time.</div>
        </div>
        <div class="step">
          <div class="step-num">2</div>
          <div><strong>Location:</strong> The interview will take place physically at the company's main office. Details will be provided in the scheduling email.</div>
        </div>
        <div class="step">
          <div class="step-num">3</div>
          <div><strong>Preparation:</strong> Be prepared to discuss your assessment results, technical choices, and past projects.</div>
        </div>
      </div>

      <p>
        If you have any immediate questions, please reply directly to this email.
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
            subject=f"🎉 Next Steps: Interview Invitation — {job_title} at {company}",
            body=html_body,
            html=True,
        )

    def send_assessment_failed_email(
        self,
        to: str,
        candidate_name: str,
        job_title: str,
        company: str,
        score: float,
        strengths: list,
        weaknesses: list,
    ) -> bool:
        """Send a rejection email with feedback and resources ("knowledge") for scoring < 80%."""
        strengths_html = "".join(f"<li>{s}</li>" for s in strengths) if strengths else "<li>Solid effort on the assessment</li>"
        weaknesses_html = "".join(f"<li>{s}</li>" for s in weaknesses) if weaknesses else "<li>Review core programming concepts</li>"

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
    .score-badge {{ display: inline-block; background: #e05555; color: white; font-size: 16px; font-weight: bold; padding: 8px 18px; border-radius: 50px; margin: 12px 0; }}
    .body {{ padding: 32px; }}
    .body p {{ color: #555; line-height: 1.7; font-size: 15px; }}
    .feedback-section {{ margin: 24px 0; padding: 20px; background: #fdfdfd; border: 1px solid #eee; border-radius: 8px; }}
    .feedback-section h3 {{ margin-top: 0; font-size: 16px; color: #1a1a2e; }}
    .box {{ padding: 12px 16px; border-radius: 6px; margin-bottom: 12px; }}
    .strengths {{ background: #f0faf5; border-left: 4px solid #3DB87A; }}
    .strengths h4 {{ color: #3DB87A; margin: 0 0 8px; }}
    .weaknesses {{ background: #fdf4f4; border-left: 4px solid #e05555; }}
    .weaknesses h4 {{ color: #e05555; margin: 0 0 8px; }}
    .feedback-section ul {{ margin: 0; padding-left: 20px; color: #444; font-size: 14px; }}
    .feedback-section li {{ margin-bottom: 6px; }}
    .footer {{ background: #1a1a2e; padding: 20px 32px; text-align: center; }}
    .footer p {{ color: #5A5A62; font-size: 12px; margin: 4px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Application Update — {job_title}</h1>
      <div class="score-badge">Score: {score:.1f}%</div>
    </div>
    <div class="body">
      <p>Dear {candidate_name},</p>
      <p>
        Thank you sincerely for completing the technical assessment for the <strong>{job_title}</strong> position at <strong>{company}</strong>.
      </p>
      <p>
        Our threshold for moving forward to the next round is 80%. Your score was <strong>{score:.1f}%</strong>.
        While we cannot move forward with your application at this stage, we want to help you build your knowledge for future opportunities.
      </p>
      
      <div class="feedback-section">
        <h3>💡 Knowledge & Assessment Feedback</h3>
        <p style="font-size: 13.5px; color: #777;">Based on our AI evaluation of your responses, here is some tailored feedback to support your professional growth:</p>
        
        <div class="box strengths">
          <h4>✅ Areas of Strength</h4>
          <ul>
            {strengths_html}
          </ul>
        </div>
        
        <div class="box weaknesses">
          <h4>📚 Recommended Areas of Study</h4>
          <ul>
            {weaknesses_html}
          </ul>
        </div>
      </div>

      <p>
        We encourage you to use this feedback to deepen your understanding. We appreciate your effort and hope to see your application again in future recruitment drives.
      </p>
      <p>
        We wish you the very best in your career and technical learning journey.
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
            subject=f"Application Feedback: {job_title} at {company}",
            body=html_body,
            html=True,
        )