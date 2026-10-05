"""Rendering and sending of HTML + plain-text emails."""

import logging
from datetime import timedelta
from math import ceil

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import EmailLog
from .unsubscribe import unsubscribe_path

log = logging.getLogger(__name__)


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
    """Transactional: always sent, never logged, no unsubscribe."""
    from accounts.magic_link import verify_path

    send(
        email,
        "Your First5K login link" if not is_signup else "Your first 2 days are one tap away",
        "magic_link",
        {"link": absolute(verify_path(raw_token)), "is_signup": is_signup},
    )


def send_to_user(user, kind: str, subject: str, template: str, context: dict | None = None,
                 ref: str = "", block=None) -> bool:
    """
    Send a non-transactional email at most once per (user, kind, ref).
    The EmailLog row is claimed first; if sending fails it is released so a later run retries.
    Returns True if an email was sent.
    """
    if not user.is_subscribed or not user.is_active:
        return False
    try:
        with transaction.atomic():
            entry = EmailLog.objects.create(user=user, kind=kind, ref=ref, block=block)
    except IntegrityError:
        return False

    unsub = absolute(unsubscribe_path(user))
    ctx = {
        "user": user,
        "unsubscribe_url": unsub,
        "account_url": absolute(reverse("accounts:account")),
        "today_url": absolute(reverse("plans:today")),
        "progress_url": absolute(reverse("plans:progress")),
        **(context or {}),
    }
    headers = {"List-Unsubscribe": f"<{unsub}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
    try:
        send(user.email, subject, template, ctx, headers)
    except Exception:
        log.exception("Sending %s to user %s failed", kind, user.pk)
        entry.delete()
        return False
    return True


def send_welcome(journey) -> bool:
    from plans import engine

    block = journey.blocks.order_by("index").first()
    return send_to_user(
        journey.user, EmailLog.Kind.WELCOME, "Welcome to First5K 👟", "welcome",
        {"level": engine.get_level(block.level), "summary": engine.session_summary(block.level)},
        block=block,
    )


# --- Progress chart for email ---------------------------------------------------------
# Email clients don't render SVG or JS, so bars are table cells with a fixed pixel height.

EMAIL_CHART_HEIGHT = 100
EMAIL_CHART_MAX_BARS = 10


def email_chart(runs: list[dict]) -> dict | None:
    recent = runs[-EMAIL_CHART_MAX_BARS:]
    if not recent:
        return None
    top = max(r["jog_minutes"] for r in recent)
    top = max(5, ceil(top / 5) * 5)
    bars = [
        {
            "number": r["number"],
            "minutes": r["jog_minutes"],
            "height": max(4, round(r["jog_minutes"] / top * EMAIL_CHART_HEIGHT)),
            "is_latest": i == len(recent) - 1,
        }
        for i, r in enumerate(recent)
    ]
    return {"bars": bars, "height": EMAIL_CHART_HEIGHT, "col_width": f"{100 / len(bars):.0f}%"}


def week_summary(stats: dict, now=None) -> dict:
    now = now or timezone.now()
    week = [r for r in stats["runs"] if r["date"] >= now - timedelta(days=7)]
    return {"runs": len(week), "minutes": sum(r["jog_minutes"] for r in week)}
