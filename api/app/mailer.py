from __future__ import annotations

import smtplib
from email.message import EmailMessage


def sanitize_header(value: str) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())


def build_message(
    *,
    sender: str,
    recipient: str,
    reply_to: str,
    subject: str,
    body: str,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sanitize_header(sender)
    message["To"] = sanitize_header(recipient)
    message["Subject"] = sanitize_header(subject)
    message["Reply-To"] = sanitize_header(reply_to)
    message.set_content(body)
    return message


def send_mail(
    *,
    host: str,
    port: int,
    sender: str,
    recipient: str,
    reply_to: str,
    subject: str,
    body: str,
) -> None:
    message = build_message(
        sender=sender,
        recipient=recipient,
        reply_to=reply_to,
        subject=subject,
        body=body,
    )
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.send_message(message)
