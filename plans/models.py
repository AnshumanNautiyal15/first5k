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
