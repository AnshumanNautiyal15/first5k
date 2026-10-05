"""
Decides which scheduled email (if any) each user should get right now, and sends it.
Run hourly via `manage.py send_scheduled_emails`. Idempotent through EmailLog.

Rules, in priority order (at most one email per user per run, and per 20 hours):
  door_open      14+ days with no activity since the block unlocked; then stay quiet until they return
  nudge          3+ days after a block unlocked with nothing completed (once per block)
  next_block     a block (not the first) has unlocked and the user hasn't opened it yet
  weekly_progress Sunday evening, if they completed something in the last 7 days
Emails only go out between 08:00 and 20:00 in the user's own timezone.
"""

from __future__ import annotations

import random
import zoneinfo
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from plans import engine, services
from plans.models import Block, Journey

from . import email as mailer
from .models import EmailLog

SEND_WINDOW = (8, 20)  # local hours [start, end)
NUDGE_AFTER = timedelta(days=3)
DOOR_OPEN_AFTER = timedelta(days=14)
MIN_SPACING = timedelta(hours=20)
WEEKLY_DAY = 6  # Sunday
WEEKLY_FROM_HOUR = 17

NEXT_BLOCK_SUBJECTS = [
    "Your next 2 days are ready 👟",
    "Fresh plan, ready when you are",
    "Psst… your next run is unlocked",
    "Two new days, made for you",
    "Ready for your next little step?",
    "Your shoes are calling (gently) 👟",
]
NUDGE_SUBJECTS = [
    "No pressure, your plan is waiting",
    "Whenever you're ready, we're here",
    "A tiny reminder (no guilt included)",
]


@dataclass
class Due:
    kind: str
    ref: str
    block: Block | None = None


def local_now(user, now: datetime) -> datetime:
    try:
        return now.astimezone(zoneinfo.ZoneInfo(user.timezone))
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return now.astimezone(zoneinfo.ZoneInfo(settings.DEFAULT_USER_TIMEZONE))


def in_send_window(user, now: datetime) -> bool:
    return SEND_WINDOW[0] <= local_now(user, now).hour < SEND_WINDOW[1]


def is_dormant(journey: Journey) -> bool:
    """We said goodbye ("door's open") and they haven't been active since."""
    return EmailLog.objects.filter(
        user=journey.user, kind=EmailLog.Kind.DOOR_OPEN, sent_at__gt=journey.last_activity_at,
    ).exists()


def due_email(journey: Journey, now: datetime) -> Due | None:
    user = journey.user
    if journey.is_complete or not user.is_subscribed or not user.is_active:
        return None
    if not in_send_window(user, now) or is_dormant(journey):
        return None
    if EmailLog.objects.filter(user=user, sent_at__gt=now - MIN_SPACING).exists():
        return None

    block = services.current_block(journey)
    if block is not None and block.unlocks_at <= now:
        ref = f"block:{block.pk}"
        nothing_done = not block.days.filter(completed_at__isnull=False).exists()
        since_unlock = now - block.unlocks_at
        idle = now - max(journey.last_activity_at, block.unlocks_at)
        sent = set(EmailLog.objects.filter(user=user, ref=ref).values_list("kind", flat=True))

        if nothing_done and idle >= DOOR_OPEN_AFTER and EmailLog.Kind.DOOR_OPEN not in sent:
            return Due(EmailLog.Kind.DOOR_OPEN, ref, block)
        if nothing_done and since_unlock >= NUDGE_AFTER and EmailLog.Kind.NUDGE not in sent:
            return Due(EmailLog.Kind.NUDGE, ref, block)
        if block.status == Block.Status.LOCKED and block.index > 1 and EmailLog.Kind.NEXT_BLOCK not in sent:
            return Due(EmailLog.Kind.NEXT_BLOCK, ref, block)

    local = local_now(user, now)
    if local.weekday() == WEEKLY_DAY and local.hour >= WEEKLY_FROM_HOUR:
        year, week, _ = local.isocalendar()
        ref = f"week:{year}-{week:02d}"
        recent = journey.blocks.filter(days__completed_at__gte=now - timedelta(days=7)).exists()
        if recent and not EmailLog.objects.filter(user=user, kind=EmailLog.Kind.WEEKLY_PROGRESS, ref=ref).exists():
            return Due(EmailLog.Kind.WEEKLY_PROGRESS, ref)
    return None


def _subject(options: list[str], seed: int) -> str:
    return options[seed % len(options)]


def send_due(journey: Journey, due: Due, now: datetime) -> bool:
    user = journey.user
    block = due.block
    ctx = {"journey": journey}
    if block is not None:
        ctx.update(level=block.level_info, summary=engine.session_summary(block.level))

    if due.kind == EmailLog.Kind.NEXT_BLOCK:
        subject = _subject(NEXT_BLOCK_SUBJECTS, block.index)
        template = "next_block"
    elif due.kind == EmailLog.Kind.NUDGE:
        subject = _subject(NUDGE_SUBJECTS, block.index)
        template = "nudge"
    elif due.kind == EmailLog.Kind.DOOR_OPEN:
        subject = "We'll leave the door open"
        template = "door_open"
    else:
        stats = services.progress_stats(journey)
        ctx.update(
            stats=stats,
            week=mailer.week_summary(stats, now),
            chart=mailer.email_chart(stats["runs"]),
        )
        subject = random.choice([
            "Your week in running 📈",
            "Look what you did this week",
            "Your progress, in one picture",
        ])
        template = "weekly_progress"
    return mailer.send_to_user(user, due.kind, subject, template, ctx, ref=due.ref, block=block)


def run(now: datetime | None = None) -> dict:
    """Send everything that's due. Returns counts per kind (for logging)."""
    now = now or timezone.now()
    counts: dict[str, int] = {}
    journeys = (
        Journey.objects.filter(completed_at__isnull=True, user__is_subscribed=True, user__is_active=True)
        .select_related("user")
    )
    for journey in journeys.iterator():
        due = due_email(journey, now)
        if due and send_due(journey, due, now):
            counts[due.kind] = counts.get(due.kind, 0) + 1
    return counts
