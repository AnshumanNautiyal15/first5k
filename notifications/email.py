"""Rendering and sending of HTML + plain-text emails."""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def absolute(path: str) -> str:
    return f"{settings.SITE_URL}{path}"


def send(to: str, subject: str, template: str, context: dict | None = None, headers: dict | None = None) -> None:
    """Send emails/<template>.txt + emails/<template>.html to one recipient."""
    ctx = {"SITE_NAME": settings.SITE_NAME, "SITE_URL": settings.SITE_URL, "subject": subject, **(context or {})}
    text = render_to_string(f"emails/{template}.txt", ctx)
    html = render_to_string(f"emails/{template}.html", ctx)
    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to], headers=headers or {})
    msg.attach_alternative(html, "text/html")
    msg.send()


def send_magic_link(email: str, raw_token: str, is_signup: bool) -> None:
    from accounts.magic_link import verify_path

    send(
        email,
        "Your First5K login link" if not is_signup else "Your first 2 days are one tap away",
        "magic_link",
        {"link": absolute(verify_path(raw_token)), "is_signup": is_signup},
    )
