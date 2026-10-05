from django.conf import settings
from django.db import models
from django.utils import timezone

from . import engine


class OnboardingStart(models.Model):
    """One row per anonymous visitor who answers the first onboarding question (funnel top)."""

    session_key = models.CharField(max_length=40, db_index=True)
    activity = models.CharField(max_length=16, choices=engine.ACTIVITY_CHOICES, blank=True)
    jog_ability = models.CharField(max_length=16, choices=engine.JOG_CHOICES, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Onboarding {self.pk} ({self.activity or '?'}/{self.jog_ability or '?'})"


class Journey(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="journey")
    start_activity = models.CharField(max_length=16, choices=engine.ACTIVITY_CHOICES, blank=True)
    start_jog_ability = models.CharField(max_length=16, choices=engine.JOG_CHOICES, blank=True)
    current_level = models.PositiveSmallIntegerField(default=1)
    blocks_completed = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Key of the last compliment shown, so we never repeat one twice in a row.
    last_message_key = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Journey of {self.user}"

    @property
    def is_complete(self):
        return self.completed_at is not None


class Block(models.Model):
    class Status(models.TextChoices):
        LOCKED = "locked", "Locked"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"

    journey = models.ForeignKey(Journey, on_delete=models.CASCADE, related_name="blocks")
    index = models.PositiveIntegerField()  # 1-based
    level = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.LOCKED, db_index=True)
    unlocks_at = models.DateTimeField(db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    feedback = models.CharField(max_length=16, choices=engine.FEEDBACK_CHOICES, blank=True)
    # Why this block looks the way it does, e.g. "welcome_back" or "ease_down" (drives copy).
    entry_note = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["index"]
        constraints = [models.UniqueConstraint(fields=["journey", "index"], name="unique_block_index")]

    def __str__(self):
        return f"Block {self.index} (level {self.level}, {self.status})"

    @property
    def level_info(self):
        return engine.get_level(self.level)

    @property
    def all_days_done(self):
        return all(d.completed_at for d in self.days.all())


class DayLog(models.Model):
    KIND_CHOICES = [("run", "Run"), ("rest", "Rest")]

    block = models.ForeignKey(Block, on_delete=models.CASCADE, related_name="days")
    day_number = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    completed_at = models.DateTimeField(null=True, blank=True)
    compliment = models.TextField(blank=True)

    class Meta:
        ordering = ["day_number"]
        constraints = [models.UniqueConstraint(fields=["block", "day_number"], name="unique_day_number")]

    def __str__(self):
        return f"{self.block} day {self.day_number} ({self.kind})"


class Milestone(models.Model):
    journey = models.ForeignKey(Journey, on_delete=models.CASCADE, related_name="milestones")
    key = models.CharField(max_length=32, choices=[(k, v["title"]) for k, v in engine.MILESTONES.items()])
    achieved_at = models.DateTimeField(default=timezone.now)
    seen_at = models.DateTimeField(null=True, blank=True)  # celebration screen shown

    class Meta:
        ordering = ["achieved_at"]
        constraints = [models.UniqueConstraint(fields=["journey", "key"], name="unique_milestone")]

    def __str__(self):
        return f"{self.journey.user}: {self.key}"

    @property
    def info(self):
        return engine.MILESTONES[self.key]
