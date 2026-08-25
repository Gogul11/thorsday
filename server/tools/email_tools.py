import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from langchain_core.tools import tool

from logger import logger
from services.user_session import get_current_user_email

load_dotenv()


@tool
def send_email(
    to_email: str,
    subject: str,
    body: str,
    sender_email: str | None = None,
) -> str:
    """Send an email to a specified recipient with a subject and body content.

    Args:
        to_email: The recipient's email address (e.g., 'colleague@example.com').
        subject: The subject line of the email.
        body: The plain-text or formatted content of the email.
        sender_email: Optional custom sender email address. If not specified,
                      the logged-in user's email address is used automatically.

    Returns:
        A status message confirming whether the email was sent or describing any errors.
    """
    from_addr = sender_email.strip() if sender_email and sender_email.strip() else get_current_user_email()
    to_addr = to_email.strip()

    smtp_server = os.getenv("SMTP_SERVER") or os.getenv("SMTP_HOST")
    smtp_port_raw = os.getenv("SMTP_PORT", "587")
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        smtp_port = 587

    smtp_username = os.getenv("SMTP_USERNAME") or os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

    # If SMTP server credentials are provided, attempt real email delivery
    if smtp_server and smtp_password:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = to_addr
            msg.set_content(body)

            if smtp_port == 465:
                # SSL connection
                with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15) as server:
                    if smtp_username and smtp_password:
                        server.login(smtp_username, smtp_password)
                    server.send_message(msg)
            else:
                # Standard SMTP / STARTTLS
                with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                    if smtp_use_tls:
                        server.starttls()
                    if smtp_username and smtp_password:
                        server.login(smtp_username, smtp_password)
                    server.send_message(msg)

            logger.info("Email sent successfully via SMTP to %s from %s", to_addr, from_addr)
            return (
                f"Email successfully sent to '{to_addr}' from '{from_addr}'.\n"
                f"Subject: {subject}\n"
                f"Delivery method: SMTP ({smtp_server}:{smtp_port})"
            )
        except Exception as exc:
            logger.exception("Failed to deliver email to %s via SMTP: %s", to_addr, exc)
            return f"Failed to send email to '{to_addr}' via SMTP: {exc}"

    # If SMTP is not configured, operate in safe simulated mode
    logger.info(
        "Email in simulated mode (no SMTP credentials configured) to %s from %s. Subject: %s",
        to_addr,
        from_addr,
        subject,
    )
    return (
        f"[SIMULATION MODE - NO ACTUAL EMAIL SENT]\n"
        f"The email was NOT sent over the network because SMTP credentials (SMTP_SERVER, SMTP_PASSWORD) are not configured in .env.\n"
        f"Simulated Details:\n"
        f"- From: {from_addr}\n"
        f"- To: {to_addr}\n"
        f"- Subject: {subject}\n"
        f"- Body:\n{body}\n\n"
        f"To send real emails, please configure SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, and SMTP_PASSWORD in server/.env."
    )


