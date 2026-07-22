import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications via SMTP."""

    @staticmethod
    def send_email(to_email: str, subject: str, body: str) -> None:
        """
        Send a text email to the target address.
        If SMTP server is not accessible or not configured, logs the email text to stdout as a fallback.
        """
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from_email
        msg["To"] = to_email
        msg.set_content(body)

        # Developer convenience / safe fallback: if smtp_host is default localhost or empty,
        # we log and skip raising error if it fails connection (only in development).
        is_local_dev = settings.app_env == "development" or settings.smtp_host in ("localhost", "127.0.0.1", "")
        
        try:
            logger.info("Connecting to SMTP server %s:%d", settings.smtp_host, settings.smtp_port)
            if settings.smtp_port == 465:
                server_class = smtplib.SMTP_SSL
            else:
                server_class = smtplib.SMTP

            with server_class(settings.smtp_host, settings.smtp_port, timeout=5) as server:
                if settings.smtp_port not in (465, 1025) and settings.smtp_host not in ("localhost", "127.0.0.1"):
                    server.ehlo()
                    try:
                        server.starttls()
                        server.ehlo()
                    except Exception as e:
                        logger.warning("STARTTLS not supported or failed: %s", e)

                if settings.smtp_username and settings.smtp_password:
                    server.login(settings.smtp_username, settings.smtp_password)

                server.send_message(msg)
                logger.info("Email successfully sent to %s with subject: '%s'", to_email, subject)
                
        except Exception as exc:
            logger.error("Failed to send email to %s via SMTP: %s", to_email, exc)
            if is_local_dev and settings.app_env != "production":
                logger.info(
                    "\n=== [DEV EMAIL FALLBACK LOG] ===\n"
                    "To: %s\n"
                    "From: %s\n"
                    "Subject: %s\n"
                    "Body:\n%s\n"
                    "=================================",
                    to_email,
                    settings.smtp_from_email,
                    subject,
                    body,
                )
            else:
                raise

    @classmethod
    def send_deadline_reminder(
        cls,
        to_email: str,
        company_name: str,
        role: str | None,
        category: str,
        deadline_str: str,
        registration_link: str | None,
    ) -> None:
        """Formulate and send a deadline reminder email."""
        category_desc = category.upper()
        subject = f"⏰ REMINDER: Upcoming Deadline for {company_name}"
        
        body = (
            f"Hello,\n\n"
            f"This is a reminder that the deadline for the following {category_desc} opportunity is approaching:\n\n"
            f"🏢 Company: {company_name}\n"
            f"💼 Role: {role or 'N/A'}\n"
            f"📅 Deadline: {deadline_str}\n"
        )
        if registration_link:
            body += f"🔗 Application Link: {registration_link}\n"
            
        body += (
            f"\nPlease make sure to complete your application before the deadline.\n\n"
            f"Best regards,\n"
            f"Deadline Sentinel AI Team"
        )
        
        cls.send_email(to_email, subject, body)
