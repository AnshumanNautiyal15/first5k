"""Tiny helpers for building test data (no factory library needed)."""

from django.contrib.auth import get_user_model

from plans import services


def make_user(email="runner@example.com", **extra):
    return get_user_model().objects.create_user(email=email, **extra)


def make_journey(user=None, activity="walks", jog="maybe", now=None):
    user = user or make_user()
    return services.create_journey(user, activity, jog, now=now)


def answer_onboarding(client, activity="walks", jog="maybe"):
    client.post("/start/", {"answer": activity})
    client.post("/start/2/", {"answer": jog})
