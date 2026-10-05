"""
Database-facing orchestration of the plan. Views call these; these call the pure engine.
All progression decisions happen here, server-side.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from . import engine, messages
from .models import Block, DayLog, Journey, OnboardingStart


def create_block(journey: Journey, *, index: int, level: int, unlocks_at, status=Block.Status.LOCKED,
                 started_at=None, entry_note: str = "") -> Block:
    block = Block.objects.create(
        journey=journey, index=index, level=level, status=status,
        unlocks_at=unlocks_at, started_at=started_at, entry_note=entry_note,
    )
    DayLog.objects.bulk_create(
        DayLog(block=block, day_number=n, kind=kind)
        for n, kind in enumerate(engine.block_layout(level), start=1)
    )
    return block


@transaction.atomic
def create_journey(user, activity: str, jog_ability: str, onboarding_start_id=None, now=None) -> Journey:
    """Create the user's journey and an active Block 1. Idempotent per user."""
    now = now or timezone.now()
    existing = Journey.objects.filter(user=user).first()
    if existing:
        return existing
    level = engine.start_level(activity, jog_ability)
    journey = Journey.objects.create(
        user=user, start_activity=activity, start_jog_ability=jog_ability,
        current_level=level, last_activity_at=now,
    )
    create_block(journey, index=1, level=level, unlocks_at=now, status=Block.Status.ACTIVE, started_at=now)
    if onboarding_start_id:
        OnboardingStart.objects.filter(pk=onboarding_start_id, user__isnull=True).update(user=user)
    return journey


def current_block(journey: Journey) -> Block | None:
    """The block the user is on: the newest active or locked one."""
    return (
        journey.blocks.filter(status__in=[Block.Status.ACTIVE, Block.Status.LOCKED])
        .order_by("-index").prefetch_related("days").first()
    )


@dataclass
class Completion:
    message: str
    already_done: bool
    block_done: bool


def _longest_completed_jog(journey: Journey, exclude_day_id: int) -> int:
    levels = (
        DayLog.objects.filter(block__journey=journey, kind="run", completed_at__isnull=False)
        .exclude(pk=exclude_day_id).values_list("block__level", flat=True)
    )
    return max((engine.get_level(lv)["continuous_minutes"] for lv in levels), default=0)


def complete_day(day: DayLog, now=None) -> Completion:
    """Mark a day complete and pick a contextual compliment. Safe to call twice."""
    now = now or timezone.now()
    with transaction.atomic():
        day = DayLog.objects.select_for_update().select_related("block__journey").get(pk=day.pk)
        block = day.block
        if day.completed_at:
            return Completion(day.compliment, already_done=True, block_done=block.all_days_done)

        journey = Journey.objects.select_for_update().get(pk=block.journey_id)
        is_first_ever = not DayLog.objects.filter(block__journey=journey, completed_at__isnull=False).exists()
        after_gap = engine.gap_kind(journey.last_activity_at, now) != engine.GAP_NORMAL
        minutes = block.level_info["continuous_minutes"]
        is_longest = day.kind == "run" and minutes > _longest_completed_jog(journey, day.pk)

        group = messages.completion_group(
            kind=day.kind, is_first_ever=is_first_ever, after_gap=after_gap, is_longest_jog=is_longest,
        )
        msg = messages.pick(group, last_key=journey.last_message_key, minutes=minutes)

        day.completed_at = now
        day.compliment = msg.text
        day.save(update_fields=["completed_at", "compliment"])
        journey.last_message_key = msg.key
        journey.last_activity_at = now
        journey.save(update_fields=["last_message_key", "last_activity_at"])

    return Completion(msg.text, already_done=False, block_done=block.all_days_done)
