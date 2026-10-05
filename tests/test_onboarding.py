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
    assert resp.url == reverse("plans:start_age")
    assert OnboardingStart.objects.get().jog_ability == "yes"
    resp = client.post(reverse("plans:start_age"), {"answer": "18_39"})
    assert resp.url == reverse("plans:preview")
    assert OnboardingStart.objects.get().age_group == "18_39"

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


def test_q3_age_question(client):
    client.post(reverse("plans:start"), {"answer": "walks"})
    client.post(reverse("plans:start_jog"), {"answer": "yes"})
    body = client.get(reverse("plans:start_age")).content.decode()
    assert "How old are you?" in body and "Question 3 of 3" in body and "65 or over" in body
    assert "gender" not in body.lower()


def test_q3_requires_q2(client):
    client.post(reverse("plans:start"), {"answer": "walks"})
    assert client.get(reverse("plans:start_age")).url == reverse("plans:start_jog")


def test_preview_requires_age(client):
    client.post(reverse("plans:start"), {"answer": "walks"})
    client.post(reverse("plans:start_jog"), {"answer": "yes"})
    assert client.get(reverse("plans:preview")).url == reverse("plans:start")


def test_older_runner_gets_capped_start(client):
    client.post(reverse("plans:start"), {"answer": "active"})
    client.post(reverse("plans:start_jog"), {"answer": "yes"})  # level 4 by default
    client.post(reverse("plans:start_age"), {"answer": "65_plus"})
    assert client.get(reverse("plans:preview")).context["level"]["number"] == 2


def test_under_18_sees_guardian_note(client):
    client.post(reverse("plans:start"), {"answer": "walks"})
    client.post(reverse("plans:start_jog"), {"answer": "maybe"})
    client.post(reverse("plans:start_age"), {"answer": "under_18"})
    assert "parent or guardian" in client.get(reverse("plans:preview")).content.decode()
