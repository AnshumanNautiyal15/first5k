"""
Create demo users at different stages of the journey for manual QA, and print a login link for each.
Development only (refuses when DEBUG is off unless --force).
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts import magic_link
from plans import engine, services
from plans.models import Block

DOMAIN = "demo.first5k.test"


def _finish(journey, feedback, at):
    block = journey.blocks.get(status="active")
    for day in block.days.all():
        services.complete_day(day, now=at)
    return services.submit_feedback(block, feedback, now=at)


def _advance(journey, blocks, start, feedback=engine.JUST_RIGHT):
    """Play through `blocks` blocks, 2 days each, starting at `start`. Returns the time after."""
    t = start
    for _ in range(blocks):
        services.refresh(journey, now=t)
        _finish(journey, feedback, t + timedelta(hours=2))
        t += timedelta(days=2, hours=3)
    return t


def build_new(user, now):
    services.create_journey(user, "sitting", "maybe", now=now - timedelta(hours=1), age_group="18_39")


def build_mid(user, now):
    j = services.create_journey(user, "walks", "maybe", now=now - timedelta(days=10), age_group="40_54")
    t = _advance(j, 3, now - timedelta(days=10))
    services.refresh(j, now=t)
    block = j.blocks.get(status="active")
    services.complete_day(block.days.get(kind="run"), now=now - timedelta(hours=3))


def build_waiting(user, now):
    j = services.create_journey(user, "walks", "yes", now=now - timedelta(days=5), age_group="18_39")
    _advance(j, 2, now - timedelta(days=5))
    services.refresh(j, now=now - timedelta(hours=6))
    _finish(j, engine.JUST_RIGHT, now - timedelta(hours=2))  # next block locked for ~2 days


def build_ready(user, now):
    """Next block has unlocked but not been opened: a 'next block ready' email is due."""
    j = services.create_journey(user, "active", "maybe", now=now - timedelta(days=4), age_group="18_39")
    _finish(j, engine.TOO_EASY, now - timedelta(days=3))


def build_halfway(user, now):
    start = now - timedelta(days=5)
    j = services.create_journey(user, "active", "yes", now=start, age_group="18_39")
    t = _advance(j, 2, start)  # 4 -> 5 -> 6, ending ~18 hours ago
    services.refresh(j, now=t)


def build_away(user, now):
    """Last active 8 days ago: sees the welcome-back message and a repeated level."""
    j = services.create_journey(user, "walks", "maybe", now=now - timedelta(days=12), age_group="55_64")
    _finish(j, engine.JUST_RIGHT, now - timedelta(days=8))  # next block unlocked then, never opened


def build_finished(user, now):
    j = services.create_journey(user, "active", "yes", now=now - timedelta(days=40), age_group="18_39")
    Block.objects.filter(journey=j).update(level=12)
    j.current_level = 12
    j.save(update_fields=["current_level"])
    _finish(j, engine.JUST_RIGHT, now - timedelta(days=1))


STAGES = [
    ("new", "Just signed up, block 1 untouched", build_new),
    ("mid", "Block 4, run day done", build_mid),
    ("waiting", "Waiting for the next block to unlock", build_waiting),
    ("ready", "Next block unlocked, not opened yet", build_ready),
    ("halfway", "Reached level 6 (halfway milestone)", build_halfway),
    ("away", "Back after 8 days away", build_away),
    ("finished", "Completed the 5K", build_finished),
]


class Command(BaseCommand):
    help = "Create demo users at different journey stages and print login links (dev only)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG is off.")

    def handle(self, *args, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError("seed_demo is for development. Use --force if you really mean it.")
        User = get_user_model()
        now = timezone.now()
        self.stdout.write(f"Demo users (links work once, for {magic_link.TOKEN_TTL.seconds // 60} minutes):\n")
        for key, description, build in STAGES:
            email = f"{key}@{DOMAIN}"
            User.objects.filter(email=email).delete()
            user = User.objects.create_user(email=email)
            build(user, now)
            raw = magic_link.issue_token(email, None)
            self.stdout.write(f"  {key:<9} {description}\n            {settings.SITE_URL}{magic_link.verify_path(raw)}")
        self.stdout.write("\nRe-run the command for fresh links.")
