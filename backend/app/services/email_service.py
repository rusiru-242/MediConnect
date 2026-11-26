import logging
import os
import smtplib
import socket
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)

# A02: plaintext SMTP is allowed only for a local test server on a loopback host (A02 integration tests and local
# UAT). Every other host must use TLS with a verified certificate.
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class EmailOutcome:
    """Result of one SMTP submission (A02-BUG-003).

    ``status`` is one of:
      * ``accepted``  - the SMTP server accepted the message (this is not proof of mailbox delivery);
      * ``rejected``  - the server refused the sender or recipient, or authentication failed (permanent);
      * ``retry``     - the connection or TLS handshake failed before the message was transmitted (safe to retry);
      * ``uncertain`` - the connection broke while or after the message was transmitted (never retried
                        automatically, because the server may already have accepted it);
      * ``disabled``  - no SMTP host is configured.

    The object is truthy only for ``accepted``, so existing ``if EmailService._send_email(...)`` callers keep their
    meaning.
    """

    __slots__ = ("status", "reason")

    def __init__(self, status: str, reason: Optional[str] = None):
        self.status, self.reason = status, reason

    def __bool__(self) -> bool:
        return self.status == "accepted"

    def __repr__(self) -> str:  # never contains addresses or content
        return f"EmailOutcome({self.status!r}, {self.reason!r})"


def outcome_of(result) -> EmailOutcome:
    """Normalise a ``_send_email`` result; test doubles may return plain booleans."""
    if isinstance(result, EmailOutcome):
        return result
    return EmailOutcome("accepted") if result else EmailOutcome("uncertain", "smtp_not_acknowledged")


def _tls_context() -> ssl.SSLContext:
    # A02-BUG-001: smtplib's default context for starttls()/SMTP_SSL is ssl._create_unverified_context(), so the
    # server certificate and host name were never checked and the SMTP password could be sent to an impostor.
    context = ssl.create_default_context(cafile=os.getenv("SMTP_CA_FILE") or None)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


class EmailService:
    """Service for sending transactional emails."""

    @classmethod
    def _send_email(cls, to_email: str, subject: str, text_content: str, html_content: str) -> EmailOutcome:
        """Submit one email via SMTP and report what is known about the outcome (see ``EmailOutcome``)."""
        from_email = settings.SMTP_FROM_EMAIL or "noreply@mediconnect.com"
        from_name = settings.SMTP_FROM_NAME or "MediConnect"

        host = (settings.SMTP_HOST or "").strip()
        if not host:
            logger.warning("SMTP_HOST is not configured. Email was skipped.")
            return EmailOutcome("disabled", "provider_not_configured")

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{from_name} <{from_email}>"
        message["To"] = to_email

        message.attach(MIMEText(text_content, "plain", "utf-8"))
        message.attach(MIMEText(html_content, "html", "utf-8"))

        port = settings.SMTP_PORT or 587
        plaintext_ok = host in _LOOPBACK and os.getenv("SMTP_ALLOW_PLAINTEXT_LOOPBACK", "").lower() == "true"
        transmitting = False
        try:
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=10, context=_tls_context())
            else:
                server = smtplib.SMTP(host, port, timeout=10)
            with server:
                server.ehlo()
                if port != 465:
                    if server.has_extn("starttls"):
                        server.starttls(context=_tls_context())
                        server.ehlo()
                    elif not plaintext_ok:
                        # Never send credentials or patient mail over an unencrypted connection.
                        return EmailOutcome("rejected", "starttls_unavailable")
                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                transmitting = True
                refused = server.sendmail(from_email, [to_email], message.as_string())
                if refused:
                    return EmailOutcome("rejected", "recipient_refused")
            logger.info("SMTP accepted email submission.")
            return EmailOutcome("accepted")
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused):
            logger.warning("SMTP refused the sender or recipient.")
            return EmailOutcome("rejected", "recipient_refused")
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed.")
            return EmailOutcome("rejected", "auth_failed")
        except smtplib.SMTPDataError as exc:
            # The server answered the DATA command with an error: it did not accept the message.
            permanent = 500 <= getattr(exc, "smtp_code", 0) < 600
            return EmailOutcome("rejected" if permanent else "retry", "data_refused")
        except (ssl.SSLError, ssl.CertificateError):
            logger.error("SMTP TLS handshake or certificate verification failed.")
            return EmailOutcome("retry" if not transmitting else "uncertain", "tls_failed")
        except (socket.timeout, TimeoutError, ConnectionError, OSError, smtplib.SMTPException) as exc:
            logger.error("SMTP submission failed (%s).", type(exc).__name__)
            if transmitting:
                return EmailOutcome("uncertain", "connection_lost_during_submission")
            return EmailOutcome("retry", "connection_failed")

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
    <h2 style="color: #1565C0; margin-top: 0;">{from_name}</h2>
    <h3 style="color: #1e293b; margin-bottom: 8px;">Verify your MediConnect account</h3>
    <p style="font-size: 15px; line-height: 1.5; color: #475569;">
      Thank you for registering with {from_name}. Use the 6-digit verification code below to verify your email address:
    </p>
    <div style="background-color: #f0f7ff; border: 1px dashed #1565C0; border-radius: 8px; text-align: center; padding: 18px; margin: 24px 0;">
      <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #1565C0;">{otp}</span>
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
    <h2 style="color: #1565C0; margin-top: 0;">{from_name}</h2>
    <h3 style="color: #1e293b; margin-bottom: 8px;">Reset your MediConnect password</h3>
    <p style="font-size: 15px; line-height: 1.5; color: #475569;">
      We received a request to reset your password for {from_name}. Use the 6-digit reset code below to proceed:
    </p>
    <div style="background-color: #f0f7ff; border: 1px dashed #1565C0; border-radius: 8px; text-align: center; padding: 18px; margin: 24px 0;">
      <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #1565C0;">{otp}</span>
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

    @classmethod
    def send_doctor_approval_email(
        cls,
        to_email: str,
        doctor_name: str,
        specialty: str,
        medical_registration_number: str,
        hospital_or_clinic: str,
        phone: Optional[str] = None,
        qualifications: Optional[str] = None,
        login_url: Optional[str] = None,
    ) -> bool:
        """Send an official approval confirmation email to an approved doctor,

        including their submitted personal details and direct doctor login portal link.
        """
        from_name = settings.SMTP_FROM_NAME or "MediConnect"
        subject = f"Congratulations! Your Doctor Application Has Been Approved - {from_name}"

        portal_url = (login_url or settings.DOCTOR_PORTAL_URL or "https://mediconnect-admin-staging.vercel.app/login").strip()
        clean_phone = phone.strip() if phone else "Not provided"
        clean_quals = qualifications.strip() if qualifications else "Standard Medical Degree"

        text_content = (
            f"Dear Dr. {doctor_name},\n\n"
            f"Congratulations! We are delighted to inform you that your doctor registration and medical credentials "
            f"have been verified and APPROVED by the {from_name} Administration Team.\n\n"
            f"Your account is now ACTIVE with full clinical access.\n\n"
            f"----------------------------------------\n"
            f"DOCTOR REGISTRATION DETAILS:\n"
            f"----------------------------------------\n"
            f"• Full Name: Dr. {doctor_name}\n"
            f"• Personal Email: {to_email}\n"
            f"• Phone Number: {clean_phone}\n"
            f"• Medical Registration (SLMC): {medical_registration_number}\n"
            f"• Medical Specialty: {specialty}\n"
            f"• Hospital / Clinic: {hospital_or_clinic}\n"
            f"• Qualifications: {clean_quals}\n"
            f"• Account Status: ACTIVE & APPROVED\n"
            f"----------------------------------------\n\n"
            f"You can now access your doctor portal and clinical dashboard using the link below:\n\n"
            f"Doctor Portal Login: {portal_url}\n\n"
            f"You may also log into the {from_name} Mobile Application using your registered email and password.\n\n"
            f"Best regards,\n"
            f"The {from_name} Medical Administration Team"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #f5f8fc; margin: 0; padding: 24px; color: #172b4d;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e5eaf2; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
    <div style="background-color: #1565C0; padding: 24px; text-align: center;">
      <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700;">{from_name}</h1>
      <p style="color: #e3f2fd; margin: 6px 0 0; font-size: 14px;">Healthcare Platform</p>
    </div>
    
    <div style="padding: 32px 28px;">
      <div style="text-align: center; margin-bottom: 24px;">
        <span style="display: inline-block; background-color: #ecfdf5; color: #16a34a; font-weight: 700; font-size: 13px; padding: 6px 14px; border-radius: 20px; border: 1px solid #a7f3d0; text-transform: uppercase; letter-spacing: 0.5px;">
          ✓ Application Approved
        </span>
        <h2 style="color: #172b4d; margin: 16px 0 8px; font-size: 22px;">Doctor Account Activated</h2>
        <p style="color: #64748b; font-size: 15px; margin: 0; line-height: 1.5;">
          Dear <strong>Dr. {doctor_name}</strong>, your professional credentials have been successfully verified. You now have full clinical access on MediConnect.
        </p>
      </div>

      <div style="background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; padding: 20px; margin-bottom: 24px;">
        <h3 style="color: #1565C0; font-size: 15px; margin: 0 0 14px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">
          Your Registered Doctor Details
        </h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
          <tr>
            <td style="padding: 6px 0; color: #64748b; width: 42%;">Full Name:</td>
            <td style="padding: 6px 0; color: #1e293b; font-weight: 600;">Dr. {doctor_name}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Personal Email:</td>
            <td style="padding: 6px 0; color: #1e293b; font-weight: 600;">{to_email}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Phone Number:</td>
            <td style="padding: 6px 0; color: #1e293b; font-weight: 600;">{clean_phone}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Registration (SLMC):</td>
            <td style="padding: 6px 0; color: #1565C0; font-weight: 700;">{medical_registration_number}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Specialty:</td>
            <td style="padding: 6px 0; color: #1e293b; font-weight: 600;">{specialty}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Hospital / Clinic:</td>
            <td style="padding: 6px 0; color: #1e293b; font-weight: 600;">{hospital_or_clinic}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Qualifications:</td>
            <td style="padding: 6px 0; color: #1e293b; font-weight: 600;">{clean_quals}</td>
          </tr>
          <tr>
            <td style="padding: 6px 0; color: #64748b;">Status:</td>
            <td style="padding: 6px 0; color: #16a34a; font-weight: 700;">ACTIVE & VERIFIED</td>
          </tr>
        </table>
      </div>

      <div style="text-align: center; margin: 28px 0;">
        <a href="{portal_url}" style="display: inline-block; background-color: #1565C0; color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: bold; font-size: 16px; box-shadow: 0 2px 6px rgba(21, 101, 192, 0.35);">
          Login to Doctor Portal
        </a>
        <p style="font-size: 13px; color: #64748b; margin-top: 12px;">
          Or copy and paste this link into your browser:<br>
          <a href="{portal_url}" style="color: #1565C0; word-break: break-all;">{portal_url}</a>
        </p>
      </div>

      <div style="background-color: #eff6ff; border-left: 4px solid #1565C0; padding: 14px 16px; border-radius: 4px; margin-top: 24px;">
        <strong style="color: #1e40af; font-size: 13px;">Mobile App Access:</strong>
        <p style="margin: 4px 0 0; font-size: 13px; color: #1e3a8a; line-height: 1.4;">
          You can also launch the <strong>MediConnect Mobile Application</strong> and sign in directly with your registered email and password to manage consultations, schedules, and patient appointments.
        </p>
      </div>

      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 28px 0 20px;">
      <p style="font-size: 12px; color: #94a3b8; margin: 0; text-align: center; line-height: 1.5;">
        This is an official automated notification from MediConnect. If you need any assistance, please contact our medical administrative support team.
      </p>
    </div>
  </div>
</body>
</html>"""
        return cls._send_email(to_email, subject, text_content, html_content)

    @classmethod
    def send_doctor_rejection_email(
        cls,
        to_email: str,
        doctor_name: str,
        reason: Optional[str] = None,
    ) -> bool:
        """Send a notification email to a doctor whose application was not approved."""
        from_name = settings.SMTP_FROM_NAME or "MediConnect"
        subject = f"Update on Your Doctor Application - {from_name}"

        clean_reason = (reason or "").strip()
        reason_text = f"\nReason: {clean_reason}\n" if clean_reason else ""
        reason_html = (
            f"""<div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
  <strong style="color: #991b1b; font-size: 13px;">Reviewer Notes:</strong>
  <p style="margin: 4px 0 0; font-size: 13px; color: #7f1d1d;">{clean_reason}</p>
</div>"""
            if clean_reason
            else ""
        )

        text_content = (
            f"Dear Dr. {doctor_name},\n\n"
            f"Thank you for your interest in joining the {from_name} network. "
            f"Following a review of your application by our medical administration team, "
            f"we regret to inform you that your registration could not be approved at this time.{reason_text}\n"
            f"If you believe this was in error or if you have updated credentials, "
            f"please contact our administrative support team.\n\n"
            f"Best regards,\n"
            f"The {from_name} Medical Administration Team"
        )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="font-family: Arial, sans-serif; background-color: #f5f8fc; margin: 0; padding: 24px; color: #172b4d;">
  <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e5eaf2; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
    <div style="background-color: #1565C0; padding: 24px; text-align: center;">
      <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700;">{from_name}</h1>
      <p style="color: #e3f2fd; margin: 6px 0 0; font-size: 14px;">Healthcare Platform</p>
    </div>
    <div style="padding: 32px 28px;">
      <h2 style="color: #172b4d; margin-top: 0; font-size: 20px;">Doctor Application Status</h2>
      <p style="font-size: 14px; line-height: 1.5; color: #475569;">
        Dear <strong>Dr. {doctor_name}</strong>, thank you for submitting your application to join {from_name}.
        Following review by our medical administration team, we regret to inform you that your registration could not be approved at this time.
      </p>
      {reason_html}
      <p style="font-size: 13px; color: #64748b; line-height: 1.5;">
        If you have questions, require clarification, or would like to submit updated credentials, please reach out to our administrative support team.
      </p>
      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
      <p style="font-size: 12px; color: #94a3b8; margin: 0; text-align: center;">
        The {from_name} Medical Administration Team
      </p>
    </div>
  </div>
</body>
</html>"""
        return cls._send_email(to_email, subject, text_content, html_content)
