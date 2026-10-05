import json

import pytest
from django.core import mail
from django.urls import reverse

from accounts import magic_link
from accounts.models import MagicLoginToken, User
from notifications.models import EmailLog
from notifications.unsubscribe import make_token, unsubscribe_path
from plans import services
from plans.models import Block, DayLog, Journey, Milestone, OnboardingStart

from .factories import make_journey, make_user

pytestmark = pytest.mark.django_db


# --- Unsubscribe ------------------------------------------------------------------------

def test_unsubscribe_get_shows_confirm_without_changing(client):
    user = make_user()
    resp = client.get(unsubscribe_path(user))
    assert resp.status_code == 200 and b"Stop plan emails?" in resp.content
    user.refresh_from_db()
    assert user.is_subscribed


def test_unsubscribe_post_without_login_or_csrf():
    from django.test import Client

    user = make_user()
    resp = Client(enforce_csrf_checks=True).post(unsubscribe_path(user), {"List-Unsubscribe": "One-Click"})
    assert resp.status_code == 200 and b"You're unsubscribed" in resp.content
    user.refresh_from_db()
    assert not user.is_subscribed


def test_unsubscribe_tampered_token(client):
    user = make_user()
    bad = make_token(user)[:-2] + "xx"
    assert client.get(reverse("notifications:unsubscribe", args=[bad])).status_code == 404


def test_unsubscribe_token_is_per_user():
    a, b = make_user("a@example.com"), make_user("b@example.com")
    assert make_token(a) != make_token(b)


# --- Account page ----------------------------------------------------------------------------

def test_account_requires_login(client):
    assert client.get(reverse("accounts:account")).status_code == 302


def test_account_settings_update(client):
    user = make_user()
    client.force_login(user)
    resp = client.post(reverse("accounts:account"), {"timezone": "Europe/London"})
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.timezone == "Europe/London" and not user.is_subscribed
    client.post(reverse("accounts:account"), {"timezone": "Europe/London", "is_subscribed": "on"})
    user.refresh_from_db()
    assert user.is_subscribed


def test_account_rejects_bogus_timezone(client):
    user = make_user()
    client.force_login(user)
    resp = client.post(reverse("accounts:account"), {"timezone": "Mars/Olympus"})
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.timezone == "Asia/Kolkata"


def test_export_contains_my_data_only(client):
    journey = make_journey()
    services.complete_day(journey.blocks.get().days.get(kind="run"))
    make_journey(make_user("other@example.com"))
    client.force_login(journey.user)
    resp = client.get(reverse("accounts:export"))
    assert resp["Content-Disposition"].startswith("attachment")
    data = json.loads(resp.content)
    assert data["account"]["email"] == journey.user.email
    assert data["journey"]["blocks"][0]["days"][0]["completed_at"]
    assert "other@example.com" not in resp.content.decode()


def test_export_without_journey(client):
    user = make_user()
    client.force_login(user)
    assert json.loads(client.get(reverse("accounts:export")).content)["journey"] is None


def test_delete_requires_confirmation(client):
    user = make_user()
    client.force_login(user)
    client.post(reverse("accounts:delete"))
    assert User.objects.filter(pk=user.pk).exists()


def test_delete_account_removes_everything(client):
    journey = make_journey()
    user = journey.user
    services.complete_day(journey.blocks.get().days.get(kind="run"))
    services.award_milestones(journey, ["first_block"])
    EmailLog.objects.create(user=user, kind="welcome")
    magic_link.issue_token(user.email, None)
    start = OnboardingStart.objects.create(session_key="s", activity="walks", user=user)

    client.force_login(user)
    resp = client.post(reverse("accounts:delete"), {"confirm": "yes"}, follow=True)
    assert b"all your data are deleted" in resp.content
    assert not User.objects.filter(pk=user.pk).exists()
    for model in (Journey, Block, DayLog, Milestone, EmailLog, MagicLoginToken):
        assert not model.objects.exists(), model
    start.refresh_from_db()
    assert start.user is None  # anonymous funnel row stays, unlinked
    assert client.get(reverse("plans:today")).status_code == 302  # logged out


def test_header_shows_account_link(client):
    journey = make_journey()
    client.force_login(journey.user)
    assert b'href="/account/"' in client.get(reverse("plans:today")).content


def test_milestone_page_has_share_card(client):
    journey = make_journey()
    services.award_milestones(journey, ["first_block"])
    client.force_login(journey.user)
    body = client.get(reverse("plans:milestone", args=["first_block"])).content.decode()
    assert "data-share-card" in body and "I just finished my first running block!" in body
    assert "share-card.js" in body
