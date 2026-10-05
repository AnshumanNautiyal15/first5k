from django.conf import settings
from django.db import models
from django.utils import timezone


class EmailLog(models.Model):
    """
    One row per non-login email sent. The unique (user, kind, ref) constraint is what
    makes the scheduled-email command idempotent: a row is claimed before sending.
    ref identifies the occasion, e.g. "block:42" or "week:2026-41" ("" for one-offs).
    """

    class Kind(models.TextChoices):
        WELCOME = "welcome", "Welcome"
        NEXT_BLOCK = "next_block", "Next block ready"
        NUDGE = "nudge", "Gentle nudge"
        DOOR_OPEN = "door_open", "Door's open (final)"
        WEEKLY_PROGRESS = "weekly_progress", "Weekly progress"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_logs")
    kind = models.CharField(max_length=32, choices=Kind.choices, db_index=True)
    ref = models.CharField(max_length=64, blank=True)
    block = models.ForeignKey("plans.Block", null=True, blank=True, on_delete=models.SET_NULL)
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-sent_at"]
        constraints = [models.UniqueConstraint(fields=["user", "kind", "ref"], name="unique_email_per_occasion")]

    def __str__(self):
        return f"{self.kind} to {self.user} ({self.ref or '-'})"
