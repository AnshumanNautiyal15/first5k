"""
Database-facing orchestration of the plan. Views call these; these call the pure engine.
All progression decisions happen here, server-side.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import engine, messages
from .models import Block, DayLog, Journey, Milestone, OnboardingStart


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
def create_journey(user, activity: str, jog_ability: str, onboarding_start_id=None, now=None,
                   age_group: str = "") -> Journey:
    """Create the user's journey and an active Block 1. Idempotent per user."""
    now = now or timezone.now()
    existing = Journey.objects.filter(user=user).first()
    if existing:
        return existing
    level = engine.start_level(activity, jog_ability, age_group)
    journey = Journey.objects.create(
        user=user, start_activity=activity, start_jog_ability=jog_ability, age_group=age_group,
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
    milestones: list[str] = field(default_factory=list)


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

        earned = award_milestones(journey, engine.milestones_after_run(block.level), now) if day.kind == "run" else []

    return Completion(msg.text, already_done=False, block_done=block.all_days_done, milestones=earned)


# --- Milestones -------------------------------------------------------------------

def award_milestones(journey: Journey, keys, now=None) -> list[str]:
    """Create any milestones not yet earned. Returns the newly earned keys, in display order."""
    now = now or timezone.now()
    have = set(journey.milestones.values_list("key", flat=True))
    new = []
    for key in (k for k in engine.MILESTONES if k in set(keys) - have):
        try:
            with transaction.atomic():
                Milestone.objects.create(journey=journey, key=key, achieved_at=now)
            new.append(key)
        except IntegrityError:  # a concurrent request already awarded it
            pass
    return new


def next_unseen_milestone(journey: Journey) -> Milestone | None:
    return journey.milestones.filter(seen_at__isnull=True).order_by("achieved_at", "pk").first()


# --- Feedback & next block ---------------------------------------------------------

@dataclass
class FeedbackResult:
    message: str
    next_block: Block | None
    journey_complete: bool
    milestones: list[str]


def previous_block(block: Block) -> Block | None:
    return Block.objects.filter(journey_id=block.journey_id, index=block.index - 1).first()


def submit_feedback(block: Block, feedback: str, now=None) -> FeedbackResult:
    """Close the active block with feedback and plan the next one (locked until unlocks_at)."""
    if feedback not in {value for value, _ in engine.FEEDBACK_CHOICES}:
        raise ValueError(f"Unknown feedback {feedback!r}")
    now = now or timezone.now()
    with transaction.atomic():
        block = Block.objects.select_for_update().get(pk=block.pk)
        journey = Journey.objects.select_for_update().get(pk=block.journey_id)
        if block.status != Block.Status.ACTIVE:
            # Double submit: report what already happened.
            nxt = journey.blocks.filter(index=block.index + 1).first()
            return FeedbackResult("", nxt, journey.is_complete, [])

        prev = previous_block(block)
        step = engine.next_level(block.level, feedback, prev.feedback if prev else None, journey.age_group)

        block.feedback = feedback
        block.completed_at = now
        block.status = Block.Status.SKIPPED if feedback == engine.DIDNT_DO else Block.Status.COMPLETED
        block.save(update_fields=["feedback", "completed_at", "status"])
        if block.status == Block.Status.COMPLETED:
            journey.blocks_completed += 1

        msg = messages.pick(f"feedback_{feedback}", last_key=journey.last_message_key)
        journey.last_message_key = msg.key
        journey.last_activity_at = now

        next_block = None
        if step.journey_complete:
            journey.completed_at = now
        else:
            started = block.started_at or block.unlocks_at
            next_block = create_block(
                journey, index=block.index + 1, level=step.level,
                unlocks_at=engine.unlock_time(
                    started, now, engine.min_gap_days(journey.age_group, settings.BLOCK_MIN_GAP_DAYS)),
            )
            journey.current_level = step.level
        journey.save()

        earned = award_milestones(
            journey, engine.milestones_after_block(journey.blocks_completed, None if step.journey_complete else step.level), now,
        )

    return FeedbackResult(msg.text, next_block, step.journey_complete, earned)


# --- Unlocking and gap rules -------------------------------------------------------

@dataclass
class Refresh:
    block: Block | None
    message: str = ""


def _rebuild_days(block: Block, level: int) -> None:
    block.days.all().delete()
    block.level = level
    DayLog.objects.bulk_create(
        DayLog(block=block, day_number=n, kind=kind) for n, kind in enumerate(engine.block_layout(level), start=1)
    )


def _gap_message(journey: Journey, kind: str) -> str:
    msg = messages.pick("ease_down" if kind == engine.GAP_EASE_DOWN else "welcome_back",
                        last_key=journey.last_message_key)
    journey.last_message_key = msg.key
    return msg.text


def refresh(journey: Journey, now=None, skip_wait: bool = False) -> Refresh:
    """
    Bring the current block up to date when the user opens the app:
    unlock a due locked block, and apply the gap rules (returning a welcome-back message once).
    """
    now = now or timezone.now()
    with transaction.atomic():
        journey = Journey.objects.select_for_update().get(pk=journey.pk)
        block = current_block(journey)
        if block is None:
            return Refresh(None)

        if block.status == Block.Status.LOCKED:
            if block.unlocks_at > now and not skip_wait:
                return Refresh(block)
            # The clock for "time away" starts once there was something to do.
            since = max(journey.last_activity_at, min(block.unlocks_at, now))
            gap = engine.gap_kind(since, now)
            level = block.level
            prev = previous_block(block)
            if gap != engine.GAP_NORMAL and prev:
                level = engine.level_after_gap(min(level, prev.level), gap)
            if level != block.level:
                _rebuild_days(block, level)
            block.status = Block.Status.ACTIVE
            block.started_at = now
            block.entry_note = gap if gap != engine.GAP_NORMAL else ""
            block.save()
            message = _gap_message(journey, gap) if gap != engine.GAP_NORMAL else ""
            journey.current_level = level
            journey.save(update_fields=["current_level", "last_message_key"])
            return Refresh(current_block(journey), message)

        # Active block left untouched for a while: restart it (gently) once.
        since = max(journey.last_activity_at, block.started_at or block.unlocks_at)
        gap = engine.gap_kind(since, now)
        if gap == engine.GAP_NORMAL:
            return Refresh(block)
        nothing_done = not block.days.filter(completed_at__isnull=False).exists()
        if gap == engine.GAP_EASE_DOWN and nothing_done:
            new_level = engine.level_after_gap(block.level, gap)
            if new_level != block.level:
                _rebuild_days(block, new_level)
                journey.current_level = new_level
        block.started_at = now
        block.entry_note = gap
        block.save()
        message = _gap_message(journey, gap)
        journey.save(update_fields=["current_level", "last_message_key"])
        return Refresh(current_block(journey), message)


def unlock_now(block: Block, now=None) -> None:
    """Admin/debug helper: make a locked block unlock immediately on the next visit."""
    now = now or timezone.now()
    Block.objects.filter(pk=block.pk, status=Block.Status.LOCKED).update(unlocks_at=now)


# --- Progress dashboard ----------------------------------------------------------------

def progress_stats(journey: Journey) -> dict:
    runs = list(
        DayLog.objects.filter(block__journey=journey, kind="run", completed_at__isnull=False)
        .select_related("block").order_by("completed_at")
    )
    run_points = [
        {
            "number": i,
            "date": d.completed_at,
            "level": d.block.level,
            "jog_minutes": engine.total_jog_minutes(d.block.level),
            "continuous_minutes": engine.get_level(d.block.level)["continuous_minutes"],
        }
        for i, d in enumerate(runs, start=1)
    ]
    rest_days = DayLog.objects.filter(block__journey=journey, kind="rest", completed_at__isnull=False).count()
    earned = {m.key: m for m in journey.milestones.all()}
    milestones = [
        {"key": k, **info, "achieved_at": earned[k].achieved_at if k in earned else None}
        for k, info in engine.MILESTONES.items()
    ]
    return {
        "runs": run_points,
        "run_count": len(run_points),
        "rest_days": rest_days,
        "total_jog_minutes": sum(p["jog_minutes"] for p in run_points),
        "longest_jog": max((p["continuous_minutes"] for p in run_points), default=0),
        "blocks_completed": journey.blocks_completed,
        "level": engine.get_level(journey.current_level),
        "milestones": milestones,
        "next_milestone": next((m for m in milestones if m["achieved_at"] is None), None),
    }
