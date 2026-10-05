import pytest
from django.urls import reverse

from plans.models import OnboardingStart

pytestmark = pytest.mark.django_db


def test_landing_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Your first 5K, 2 days at a time." in resp.content
    assert b"Start my first 2 days" in resp.content
    assert b"No password. No spam." in resp.content


def test_q1_shows_choices(client):
    resp = client.get(reverse("plans:start"))
    assert resp.status_code == 200
    assert b"How active are you right now?" in resp.content
    assert b"Mostly sitting" in resp.content


def test_q1_answer_saved_and_redirects(client):
    resp = client.post(reverse("plans:start"), {"answer": "walks"})
    assert resp.status_code == 302
    assert resp.url == reverse("plans:start_jog")
    assert client.session["onboarding"]["activity"] == "walks"
    start = OnboardingStart.objects.get()
    assert start.activity == "walks"


def test_q1_invalid_answer_rerenders(client):
    resp = client.post(reverse("plans:start"), {"answer": "marathoner"})
    assert resp.status_code == 200
    assert "onboarding" not in client.session
    assert OnboardingStart.objects.count() == 0


def test_q1_answered_twice_reuses_funnel_row(client):
    client.post(reverse("plans:start"), {"answer": "walks"})
    client.post(reverse("plans:start"), {"answer": "active"})
    assert OnboardingStart.objects.get().activity == "active"


def test_q2_requires_q1(client):
    resp = client.get(reverse("plans:start_jog"))
    assert resp.status_code == 302
    assert resp.url == reverse("plans:start")


def test_full_flow_to_preview(client):
    client.post(reverse("plans:start"), {"answer": "walks"})
    resp = client.post(reverse("plans:start_jog"), {"answer": "yes"})
    assert resp.url == reverse("plans:preview")
    assert OnboardingStart.objects.get().jog_ability == "yes"

    resp = client.get(reverse("plans:preview"))
    assert resp.status_code == 200
    # walks + yes -> level 3
    assert resp.context["level"]["number"] == 3
    body = resp.content.decode()
    assert "Jog for 2 minutes, then walk for 2 minutes. Do this 5 times." in body
    assert "Talk test" in body
    assert "Walking is always allowed" in body
    assert "Not medical advice" in body


def test_preview_requires_onboarding(client):
    resp = client.get(reverse("plans:preview"))
    assert resp.status_code == 302
    assert resp.url == reverse("plans:start")


def test_onboarding_post_requires_csrf():
    from django.test import Client

    csrf_client = Client(enforce_csrf_checks=True)
    resp = csrf_client.post(reverse("plans:start"), {"answer": "walks"})
    assert resp.status_code == 403
