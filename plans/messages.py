"""
Compliments and encouragement. Pure Python, no Django.

Messages are grouped by situation. Each message gets a stable key "<group>:<index>"
so we can avoid showing the same one twice in a row. Light templating with
str.format: e.g. {minutes}, {level_title}.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

MESSAGES: dict[str, list[str]] = {
    # The very first day ever marked complete.
    "first_ever": [
        "You did it! Your very first day is done. That's the hardest one, and it's behind you now.",
        "Day one: done. Most people only think about starting. You actually started.",
        "Look at you! First day complete. Remember this feeling.",
        "That first step out the door is the biggest one. You took it. 🎉",
    ],
    # A normal run day.
    "standard": [
        "Another run in the bag. Nicely done!",
        "You showed up, and that's what counts. Great work.",
        "Done! Your legs might not say it, but they're grateful.",
        "That's one more run than yesterday. Brilliant.",
        "Slow or fast, it all counts. And today counted.",
        "You kept your promise to yourself today. That matters.",
        "Run done. Go enjoy the rest of your day, you earned it.",
        "Every run makes the next one a little easier. Well done.",
    ],
    # First completion after 5+ days away.
    "after_gap": [
        "Welcome back, and well done! Picking it back up is a real skill.",
        "You came back. That's the part that really matters. Great run.",
        "Life happens. You still showed up today, and that's brilliant.",
        "Back at it! It doesn't matter how long it's been, only that you're here.",
    ],
    # Longest continuous jog so far.
    "harder_level": [
        "{minutes} minutes of jogging, that's your longest yet!",
        "New personal best: {minutes} minutes without stopping. Wow.",
        "{minutes} minutes straight! A few weeks ago that might have sounded impossible.",
        "You just jogged {minutes} minutes in one go. Your body is getting stronger.",
        "Longest jog so far: {minutes} minutes. Take a moment to enjoy that.",
    ],
    # Rest day marked done.
    "rest": [
        "Rest day done. Recovery is part of training, honestly.",
        "Nice! Resting is how your body turns effort into progress.",
        "Rest: complete. Your muscles are quietly rebuilding.",
        "A good rest day is a smart day. Well done.",
    ],
    # Milestones (bigger moments).
    "milestone_first_block": [
        "Your first block is done! You're officially a runner-in-progress.",
        "One block down. You've already done more than most people who say 'one day'.",
    ],
    "milestone_five_minutes": [
        "Five whole minutes without stopping. That's a huge moment, be proud.",
        "5 minutes of continuous jogging! This is where it starts to click.",
    ],
    "milestone_halfway": [
        "You're halfway to your 5K. Look how far you've come.",
        "Halfway there! The hardest part was starting, and you nailed that long ago.",
    ],
    "milestone_five_k": [
        "You ran your first 5K. You. Did. It. 🏅",
        "5K complete! From the first slow minute to this. Incredible.",
    ],
    # Shown when returning after a gap.
    "welcome_back": [
        "Welcome back! We kept your spot warm. Let's pick up right where you left off.",
        "Hey, good to see you! No catching up needed, just the next 2 days.",
        "You're back, and that's what matters. Your next 2 days are ready.",
    ],
    "ease_down": [
        "Welcome back! We've made the next 2 days a touch gentler so you can ease back in.",
        "So good to see you again. We've dialled things back a little to help you settle in.",
    ],
    # Acknowledging block feedback.
    "feedback_too_easy": [
        "Love that! We'll nudge things up a little next time.",
        "Feeling strong! Your next 2 days will be a small step up.",
    ],
    "feedback_just_right": [
        "Just right is perfect. We'll take a gentle step forward.",
        "That's the sweet spot. Next 2 days: a small step up.",
    ],
    "feedback_too_hard": [
        "Thanks for telling us. We'll keep things at this level until it feels better.",
        "Totally fine. Hard days are part of it. We'll keep the next 2 days familiar.",
    ],
    "feedback_didnt_do": [
        "No problem at all. We'll keep these days waiting for you, no pressure.",
        "That's okay! Life gets busy. Same plan, whenever you're ready.",
    ],
}


@dataclass(frozen=True)
class Message:
    key: str
    text: str


def pick(group: str, last_key: str = "", rng: random.Random | None = None, **context) -> Message:
    """Pick a message from a group, never repeating last_key if there's another option."""
    rng = rng or random
    options = [(f"{group}:{i}", text) for i, text in enumerate(MESSAGES[group])]
    fresh = [o for o in options if o[0] != last_key] or options
    key, text = rng.choice(fresh)
    return Message(key=key, text=text.format(**context))


def completion_group(*, kind: str, is_first_ever: bool, after_gap: bool, is_longest_jog: bool) -> str:
    """Choose which group a day-completion compliment comes from. Most specific wins."""
    if is_first_ever:
        return "first_ever"
    if kind == "rest":
        return "rest"
    if after_gap:
        return "after_gap"
    if is_longest_jog:
        return "harder_level"
    return "standard"
