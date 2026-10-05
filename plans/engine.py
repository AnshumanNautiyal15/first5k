"""
The First5K progression engine.

Pure Python: no Django imports, no database. Everything here takes plain
values and returns plain values so it can be unit tested exhaustively.
The DB-facing orchestration lives in plans/services.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

WARMUP_MINUTES = 5
COOLDOWN_MINUTES = 5

# --- Levels -----------------------------------------------------------------
# Levels are data. Each run session = warm-up walk + main part + cool-down walk.
# kind: "intervals" (jog/walk repeats), "continuous" (one jog), "5k" (the goal).
LEVELS: list[dict] = [
    {
        "number": 1, "kind": "intervals", "jog_seconds": 60, "walk_seconds": 120, "repeats": 6,
        "continuous_minutes": 1,
        "title": "Your first steps",
        "description": "Tiny bits of jogging with plenty of walking in between.",
        "tip": "Jog so slowly it almost feels silly. That's exactly right.",
    },
    {
        "number": 2, "kind": "intervals", "jog_seconds": 60, "walk_seconds": 90, "repeats": 8,
        "continuous_minutes": 1,
        "title": "Finding a rhythm",
        "description": "Short jogs with a little less walking in between.",
        "tip": "Your breathing will get a bit faster. That's your body waking up, not a problem.",
    },
    {
        "number": 3, "kind": "intervals", "jog_seconds": 120, "walk_seconds": 120, "repeats": 5,
        "continuous_minutes": 2,
        "title": "Two minutes at a time",
        "description": "Equal parts jogging and walking.",
        "tip": "If the jog feels long, slow it down. Speed doesn't matter at all.",
    },
    {
        "number": 4, "kind": "intervals", "jog_seconds": 180, "walk_seconds": 120, "repeats": 4,
        "continuous_minutes": 3,
        "title": "Three-minute jogs",
        "description": "Jogging stretches get a little longer.",
        "tip": "The first minute of each jog is often the hardest. It usually settles.",
    },
    {
        "number": 5, "kind": "intervals", "jog_seconds": 240, "walk_seconds": 120, "repeats": 4,
        "continuous_minutes": 4,
        "title": "Four-minute jogs",
        "description": "You're building real staying power now.",
        "tip": "Try relaxing your shoulders and hands while you jog.",
    },
    {
        "number": 6, "kind": "intervals", "jog_seconds": 300, "walk_seconds": 120, "repeats": 3,
        "continuous_minutes": 5,
        "title": "Five minutes straight",
        "description": "Three jogs of five minutes each.",
        "tip": "Five minutes is a big deal. Pick a slow, comfy pace and settle in.",
    },
    {
        "number": 7, "kind": "intervals", "jog_seconds": 480, "walk_seconds": 120, "repeats": 2,
        "continuous_minutes": 8,
        "title": "Eight-minute jogs",
        "description": "Two longer jogs with a walk in the middle.",
        "tip": "Break it into small pieces in your head: one lamppost, one song at a time.",
    },
    {
        "number": 8, "kind": "intervals", "jog_seconds": 600, "walk_seconds": 120, "repeats": 2,
        "continuous_minutes": 10,
        "title": "Ten-minute jogs",
        "description": "Two ten-minute jogs. You've come a long way.",
        "tip": "A podcast or playlist can make ten minutes fly by.",
    },
    {
        "number": 9, "kind": "intervals", "jog_seconds": 720, "walk_seconds": 120, "repeats": 2,
        "continuous_minutes": 12,
        "title": "Twelve-minute jogs",
        "description": "The last interval level before going continuous.",
        "tip": "If you need a short walk mid-jog, take it. Walking is always allowed.",
    },
    {
        "number": 10, "kind": "continuous", "jog_seconds": 1200, "walk_seconds": 0, "repeats": 1,
        "continuous_minutes": 20,
        "title": "Twenty minutes, no stopping",
        "description": "One steady jog. Slow and steady wins this one.",
        "tip": "Start slower than you think you need to. You can always speed up later.",
    },
    {
        "number": 11, "kind": "continuous", "jog_seconds": 1500, "walk_seconds": 0, "repeats": 1,
        "continuous_minutes": 25,
        "title": "Twenty-five minutes",
        "description": "Nearly there. One relaxed, continuous jog.",
        "tip": "Notice how far you've come. A few weeks ago, one minute was the goal.",
    },
    {
        "number": 12, "kind": "5k", "jog_seconds": 0, "walk_seconds": 0, "repeats": 1,
        "continuous_minutes": 30,
        "title": "Your 5K",
        "description": "About 5 km at an easy pace. Walk breaks allowed, no time target.",
        "tip": "This is your day. Go easy, enjoy it, and walk whenever you want.",
    },
]
MAX_LEVEL = len(LEVELS)
MIN_LEVEL = 1


def get_level(number: int) -> dict:
    return LEVELS[clamp_level(number) - 1]


def clamp_level(number: int) -> int:
    return max(MIN_LEVEL, min(MAX_LEVEL, number))


# --- Block layout -------------------------------------------------------------
# A block is a fixed sequence of days. Default: one run day + one rest day.
# Override per level here later, e.g. {11: ("run", "run")}.
DEFAULT_BLOCK_LAYOUT: tuple[str, ...] = ("run", "rest")
BLOCK_LAYOUT_OVERRIDES: dict[int, tuple[str, ...]] = {}

REST_DAY_TEXT = "Rest, or a relaxed 20–30 min walk if you feel like it."


def block_layout(level: int) -> tuple[str, ...]:
    return BLOCK_LAYOUT_OVERRIDES.get(clamp_level(level), DEFAULT_BLOCK_LAYOUT)


# --- Plain-language session description ---------------------------------------

def _duration(seconds: int) -> str:
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"
    return f"{seconds} seconds"


def session_steps(level: int) -> list[str]:
    """Ordered, plain-language steps for a run day at this level."""
    lvl = get_level(level)
    steps = [f"Walk briskly for {WARMUP_MINUTES} minutes to warm up."]
    if lvl["kind"] == "intervals":
        steps.append(
            f"Jog for {_duration(lvl['jog_seconds'])}, then walk for "
            f"{_duration(lvl['walk_seconds'])}. Do this {lvl['repeats']} times."
        )
    elif lvl["kind"] == "continuous":
        steps.append(f"Jog slowly for {_duration(lvl['jog_seconds'])} without stopping.")
    else:
        steps.append("Cover about 5 km at an easy pace. Walk breaks are welcome. No clock, no target.")
    steps.append(f"Walk gently for {COOLDOWN_MINUTES} minutes to cool down.")
    return steps


def session_summary(level: int) -> str:
    lvl = get_level(level)
    if lvl["kind"] == "intervals":
        return f"Jog {_duration(lvl['jog_seconds'])} / walk {_duration(lvl['walk_seconds'])} × {lvl['repeats']}"
    if lvl["kind"] == "continuous":
        return f"Jog {_duration(lvl['jog_seconds'])} continuously"
    return "About 5 km, easy pace"


def session_total_minutes(level: int) -> int | None:
    """Approximate total session time; None for the open-ended 5K."""
    lvl = get_level(level)
    if lvl["kind"] == "5k":
        return None
    main = (lvl["jog_seconds"] + lvl["walk_seconds"]) * lvl["repeats"]
    return WARMUP_MINUTES + COOLDOWN_MINUTES + round(main / 60)


# --- Starting level -----------------------------------------------------------

ACTIVITY_CHOICES = [
    ("sitting", "Mostly sitting"),
    ("walks", "I walk regularly"),
    ("active", "I'm already fairly active"),
]
JOG_CHOICES = [
    ("not_yet", "Not yet"),
    ("maybe", "Maybe"),
    ("yes", "Yes"),
]

_START_LEVELS = {
    ("sitting", "not_yet"): 1,
    ("sitting", "maybe"): 1,
    ("sitting", "yes"): 2,
    ("walks", "not_yet"): 1,
    ("walks", "maybe"): 2,
    ("walks", "yes"): 3,
    ("active", "not_yet"): 2,
    ("active", "maybe"): 3,
    ("active", "yes"): 4,
}


def start_level(activity: str, jog_ability: str) -> int:
    """Map onboarding answers to a starting level. Unknown answers start at 1."""
    return _START_LEVELS.get((activity, jog_ability), MIN_LEVEL)


# --- Progression after feedback -----------------------------------------------

TOO_EASY = "too_easy"
JUST_RIGHT = "just_right"
TOO_HARD = "too_hard"
DIDNT_DO = "didnt_do"
FEEDBACK_CHOICES = [
    (TOO_EASY, "Too easy"),
    (JUST_RIGHT, "Just right"),
    (TOO_HARD, "Too hard"),
    (DIDNT_DO, "I couldn't do these days"),
]


@dataclass(frozen=True)
class NextStep:
    level: int
    journey_complete: bool = False


def next_level(current: int, feedback: str, previous_feedback: str | None = None) -> NextStep:
    """
    Decide the next block's level from this block's feedback.

    previous_feedback is the feedback given on the block before this one
    (None if there wasn't one), used for the "twice in a row" rules.
    """
    current = clamp_level(current)

    if current == MAX_LEVEL and feedback in (TOO_EASY, JUST_RIGHT):
        return NextStep(level=MAX_LEVEL, journey_complete=True)

    if feedback == TOO_EASY:
        step = 2 if previous_feedback == TOO_EASY else 1
        return NextStep(clamp_level(current + step))
    if feedback == JUST_RIGHT:
        return NextStep(clamp_level(current + 1))
    if feedback == TOO_HARD:
        if previous_feedback == TOO_HARD:
            return NextStep(clamp_level(current - 1))
        return NextStep(current)
    # DIDNT_DO (or anything unknown): repeat, never punish.
    return NextStep(current)


# --- Gap rules ------------------------------------------------------------------

GAP_NORMAL = "normal"
GAP_WELCOME_BACK = "welcome_back"  # 5–13 days: repeat current block
GAP_EASE_DOWN = "ease_down"        # 14+ days: drop one level

WELCOME_BACK_AFTER_DAYS = 5
EASE_DOWN_AFTER_DAYS = 14


def gap_kind(since: datetime, now: datetime) -> str:
    days = (now - since).days
    if days >= EASE_DOWN_AFTER_DAYS:
        return GAP_EASE_DOWN
    if days >= WELCOME_BACK_AFTER_DAYS:
        return GAP_WELCOME_BACK
    return GAP_NORMAL


def level_after_gap(level: int, kind: str) -> int:
    if kind == GAP_EASE_DOWN:
        return clamp_level(level - 1)
    return clamp_level(level)


# --- Unlock timing ------------------------------------------------------------

def unlock_time(previous_started_at: datetime, finished_at: datetime, min_gap_days: int) -> datetime:
    """Next block unlocks min_gap_days after the previous one started, or when it was finished, whichever is later."""
    return max(previous_started_at + timedelta(days=min_gap_days), finished_at)


# --- Milestones ---------------------------------------------------------------

MILESTONE_FIRST_BLOCK = "first_block"
MILESTONE_FIVE_MINUTES = "five_minutes"
MILESTONE_HALFWAY = "halfway"
MILESTONE_FIVE_K = "five_k"

MILESTONES: dict[str, dict] = {
    MILESTONE_FIRST_BLOCK: {"title": "First block done!", "emoji": "🌱",
                            "share_text": "I just finished my first running block!"},
    MILESTONE_FIVE_MINUTES: {"title": "5 minutes without stopping!", "emoji": "🔥",
                             "share_text": "I just jogged 5 minutes without stopping!"},
    MILESTONE_HALFWAY: {"title": "Halfway there!", "emoji": "⛰️",
                        "share_text": "I'm halfway to my first 5K!"},
    MILESTONE_FIVE_K: {"title": "You ran your first 5K!", "emoji": "🏅",
                       "share_text": "I just finished my first 5K!"},
}
HALFWAY_LEVEL = 6


def milestones_after_run(completed_run_level: int) -> set[str]:
    """Milestones earned by completing a run day at this level."""
    earned = set()
    if get_level(completed_run_level)["continuous_minutes"] >= 5:
        earned.add(MILESTONE_FIVE_MINUTES)
    if completed_run_level == MAX_LEVEL:
        earned.add(MILESTONE_FIVE_K)
    return earned


def milestones_after_block(blocks_completed: int, next_block_level: int | None) -> set[str]:
    """Milestones earned when a block is finished and the next one is planned."""
    earned = set()
    if blocks_completed >= 1:
        earned.add(MILESTONE_FIRST_BLOCK)
    if next_block_level is not None and next_block_level >= HALFWAY_LEVEL:
        earned.add(MILESTONE_HALFWAY)
    return earned


# --- Progress -----------------------------------------------------------------

def estimated_total_blocks(block_index: int, level: int) -> int:
    """'Block N of about M': blocks so far plus one block per remaining level."""
    return block_index + (MAX_LEVEL - clamp_level(level))


def coming_up_hint(level: int) -> str | None:
    """A gentle hint about the next noticeable step up. Never the full schedule."""
    current = get_level(level)
    for lvl in LEVELS[current["number"]:]:
        if lvl["kind"] == "5k":
            return "Soon you'll be heading out for your very first 5K."
        if lvl["continuous_minutes"] > current["continuous_minutes"]:
            minutes = lvl["continuous_minutes"]
            unit = "minute" if minutes == 1 else "minutes"
            return f"Soon you'll be jogging {minutes} {unit} straight."
    return None
