import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending transactional emails."""

    @classmethod
    def _send_email(cls, to_email: str, subject: str, text_content: str, html_content: str) -> bool:
        """Internal helper to dispatch emails via SMTP."""
        from_email = settings.SMTP_FROM_EMAIL or "noreply@mediconnect.com"
        from_name = settings.SMTP_FROM_NAME or "MediConnect"

        if not settings.SMTP_HOST or not settings.SMTP_HOST.strip():
            logger.warning(
                "SMTP_HOST is not configured. Email to %s was skipped (simulation mode).",
                to_email,
            )
            return False

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{from_name} <{from_email}>"
        message["To"] = to_email

        message.attach(MIMEText(text_content, "plain"))
        message.attach(MIMEText(html_content, "html"))

        try:
            port = settings.SMTP_PORT or 587
            if port == 465:
                with smtplib.SMTP_SSL(settings.SMTP_HOST, port, timeout=10) as server:
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(from_email, [to_email], message.as_string())
            else:
                with smtplib.SMTP(settings.SMTP_HOST, port, timeout=10) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(from_email, [to_email], message.as_string())
            logger.info("Email '%s' successfully sent to %s.", subject, to_email)
            return True
        except Exception as exc:
            logger.error("Failed to deliver email to %s: %s", to_email, type(exc).__name__)
            return False

    @classmethod
    def send_verification_otp(cls, to_email: str, otp: str) -> bool:
        """Send a 6-digit email verification OTP to a user."""
        from_name = settings.SMTP_FROM_NAME or "MediConnect"
        subject = "Verify your MediConnect account"

        text_content = (
            f"Hello,\n\n"
            f"Thank you for registering with {from_name}.\n\n"
            f"Your 6-digit email verification code is: {otp}\n\n"
            f"This code will expire in 10 minutes.\n\n"
            f"Security note: Do NOT share this code with anyone. MediConnect staff will never ask for your verification code.\n\n"
            f"If you did not request this registration, please disregard this email.\n\n"
            f"Best regards,\n"
            f"The {from_name} Team"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #f7f9fc; margin: 0; padding: 24px; color: #333333;">
  <div style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; padding: 32px;">
    <h2 style="color: #0f766e; margin-top: 0;">{from_name}</h2>
    <h3 style="color: #1e293b; margin-bottom: 8px;">Verify your MediConnect account</h3>
    <p style="font-size: 15px; line-height: 1.5; color: #475569;">
      Thank you for registering with {from_name}. Use the 6-digit verification code below to verify your email address:
    </p>
    <div style="background-color: #f0fdfa; border: 1px dashed #0f766e; border-radius: 8px; text-align: center; padding: 18px; margin: 24px 0;">
      <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #0f766e;">{otp}</span>
    </div>
    <p style="font-size: 14px; color: #64748b;">
      This verification code is valid for <strong>10 minutes</strong>.
    </p>
    <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; margin-top: 20px; border-radius: 4px;">
      <strong style="color: #991b1b; font-size: 13px;">Security Note:</strong>
      <p style="margin: 4px 0 0; font-size: 13px; color: #7f1d1d;">
        Do NOT share this code with anyone. MediConnect will never ask for your verification code.
      </p>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
    <p style="font-size: 12px; color: #94a3b8; margin: 0;">
      If you did not sign up for MediConnect, you can safely ignore this email.
    </p>
  </div>
</body>
</html>"""
        return cls._send_email(to_email, subject, text_content, html_content)

    @classmethod
    def send_password_reset_otp(cls, to_email: str, otp: str) -> bool:
        """Send a 6-digit password reset OTP to a user."""
        from_name = settings.SMTP_FROM_NAME or "MediConnect"
        subject = "Reset your MediConnect password"

        text_content = (
            f"Hello,\n\n"
            f"We received a request to reset your password for {from_name}.\n\n"
            f"Your 6-digit password reset code is: {otp}\n\n"
            f"This code will expire in 10 minutes.\n\n"
            f"Security note: Do NOT share this code with anyone. MediConnect staff will never ask for your verification code.\n\n"
            f"If you did not request a password reset, please ignore this email and your password will remain unchanged.\n\n"
            f"Best regards,\n"
            f"The {from_name} Team"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #f7f9fc; margin: 0; padding: 24px; color: #333333;">
  <div style="max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; padding: 32px;">
    <h2 style="color: #0f766e; margin-top: 0;">{from_name}</h2>
    <h3 style="color: #1e293b; margin-bottom: 8px;">Reset your MediConnect password</h3>
    <p style="font-size: 15px; line-height: 1.5; color: #475569;">
      We received a request to reset your password for {from_name}. Use the 6-digit reset code below to proceed:
    </p>
    <div style="background-color: #f0fdfa; border: 1px dashed #0f766e; border-radius: 8px; text-align: center; padding: 18px; margin: 24px 0;">
      <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #0f766e;">{otp}</span>
    </div>
    <p style="font-size: 14px; color: #64748b;">
      This password reset code is valid for <strong>10 minutes</strong>.
    </p>
    <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; margin-top: 20px; border-radius: 4px;">
      <strong style="color: #991b1b; font-size: 13px;">Security Note:</strong>
      <p style="margin: 4px 0 0; font-size: 13px; color: #7f1d1d;">
        Do NOT share this code with anyone. MediConnect will never ask for your reset code.
      </p>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
    <p style="font-size: 12px; color: #94a3b8; margin: 0;">
      If you did not request a password reset, you can safely ignore this email.
    </p>
  </div>
</body>
</html>"""
        return cls._send_email(to_email, subject, text_content, html_content)
