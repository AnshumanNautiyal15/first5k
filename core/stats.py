"""Funnel numbers for the admin stats page."""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from plans import engine
from plans.models import Journey, OnboardingStart

PERIODS = {"7": 7, "30": 30, "90": 90, "all": None}


def funnel(days: int | None = None, now=None) -> dict:
    """Cohort funnel: everyone who started onboarding / signed up within the period."""
    now = now or timezone.now()
    starts = OnboardingStart.objects.all()
    journeys = Journey.objects.filter(user__is_staff=False)
    if days is not None:
        since = now - timedelta(days=days)
        starts = starts.filter(created_at__gte=since)
        journeys = journeys.filter(created_at__gte=since)

    steps = [
        ("Onboarding started", starts.count()),
        ("Signed up (verified email)", journeys.count()),
        ("First block completed", journeys.filter(blocks_completed__gte=1).count()),
        ("Second block started", journeys.filter(blocks__index=2, blocks__started_at__isnull=False).distinct().count()),
        ("Reached block 6+", journeys.filter(blocks__index__gte=6, blocks__started_at__isnull=False).distinct().count()),
    ]
    top = steps[0][1] or 0
    rows = []
    prev = None
    for label, count in steps:
        rows.append({
            "label": label,
            "count": count,
            "of_top": round(100 * count / top) if top else None,
            "of_prev": round(100 * count / prev) if prev else None,
            "bar": round(100 * count / top) if top else 0,
        })
        prev = count

    by_age = dict(journeys.values_list("age_group").annotate(n=Count("id")))
    ages = [(label, by_age.get(value, 0)) for value, label in engine.AGE_CHOICES]
    if by_age.get(""):
        ages.append(("Not asked", by_age[""]))
    return {"rows": rows, "ages": ages, "finished": journeys.filter(completed_at__isnull=False).count()}
