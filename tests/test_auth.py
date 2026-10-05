import re
from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from accounts import magic_link
from accounts.models import MagicLoginToken, User
from plans.models import Journey, OnboardingStart

from .factories import answer_onboarding, make_user

pytestmark = pytest.mark.django_db


def link_from_mail(message) -> str:
    return re.search(r"https?://\S+/auth/verify/[\w-]+/", message.body).group(0)


def latest_link() -> str:
    """Path of the most recent magic link sent."""
    msg = [m for m in mail.outbox if "/auth/verify/" in m.body][-1]
    return path_of(link_from_mail(msg))


def path_of(url: str) -> str:
    return re.sub(r"^https?://[^/]+", "", url)


# --- Token storage --------------------------------------------------------------

def test_only_hash_is_stored():
    raw = magic_link.issue_token("a@example.com", "1.2.3.4")
    token = MagicLoginToken.objects.get()
    assert token.token_hash == magic_link.hash_token(raw)
    assert raw not in token.token_hash
    assert len(token.token_hash) == 64


def test_token_expires_after_15_minutes():
    raw = magic_link.issue_token("a@example.com", None)
    MagicLoginToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert magic_link.redeem(raw) is None
    assert not User.objects.exists()


def test_token_is_single_use():
    raw = magic_link.issue_token("a@example.com", None)
    assert magic_link.redeem(raw) is not None
    assert magic_link.redeem(raw) is None


def test_redeem_invalidates_other_outstanding_links():
    first = magic_link.issue_token("a@example.com", None)
    second = magic_link.issue_token("a@example.com", None)
    assert magic_link.redeem(second) is not None
    assert magic_link.redeem(first) is None


def test_unknown_token_rejected():
    assert magic_link.redeem("nope") is None


def test_user_created_only_on_verify_with_unusable_password():
    raw = magic_link.issue_token("new@example.com", None)
    assert not User.objects.exists()
    redeemed = magic_link.redeem(raw)
    assert redeemed.created
    assert not redeemed.user.has_usable_password()


# --- Rate limiting --------------------------------------------------------------

def test_rate_limit_per_email():
    for i in range(5):
        magic_link.issue_token("a@example.com", f"10.0.0.{i}")
    assert magic_link.is_rate_limited("a@example.com", "10.0.0.99")


def test_rate_limit_per_ip():
    for i in range(5):
        magic_link.issue_token(f"u{i}@example.com", "10.0.0.1")
    assert magic_link.is_rate_limited("fresh@example.com", "10.0.0.1")


def test_rate_limit_window_is_one_hour():
    for _ in range(5):
        magic_link.issue_token("a@example.com", "10.0.0.1")
    MagicLoginToken.objects.update(created_at=timezone.now() - timedelta(minutes=61))
    assert not magic_link.is_rate_limited("a@example.com", "10.0.0.1")


def test_login_view_rate_limited_message(client):
    for _ in range(5):
        client.post(reverse("accounts:login"), {"email": "a@example.com"})
    assert len(mail.outbox) == 5
    resp = client.post(reverse("accounts:login"), {"email": "a@example.com"})
    assert resp.status_code == 200
    assert b"a few links already" in resp.content
    assert len(mail.outbox) == 5


# --- Views ------------------------------------------------------------------------

def test_login_response_does_not_reveal_whether_email_exists(client):
    make_user("known@example.com")
    client.post(reverse("accounts:login"), {"email": "known@example.com"})
    known = client.get(reverse("accounts:check_email")).content
    client.post(reverse("accounts:login"), {"email": "unknown@example.com"})
    unknown = client.get(reverse("accounts:check_email")).content
    assert known == unknown
    assert b"If that email is valid" in known


def test_invalid_email_shows_friendly_error(client):
    resp = client.post(reverse("accounts:login"), {"email": "not-an-email"})
    assert resp.status_code == 200
    assert b"look like an email address" in resp.content
    assert not mail.outbox


def test_verify_get_does_not_consume_token(client):
    raw = magic_link.issue_token("a@example.com", None)
    resp = client.get(reverse("accounts:verify", args=[raw]))
    assert resp.status_code == 200
    assert b"Open my plan" in resp.content
    assert MagicLoginToken.objects.get().used_at is None


def test_verify_expired_link_shows_friendly_page(client):
    resp = client.get(reverse("accounts:verify", args=["bogus"]))
    assert resp.status_code == 410
    assert b"This link has expired" in resp.content


def test_full_signup_flow_creates_journey_and_block_one(client):
    answer_onboarding(client, "walks", "yes")  # -> level 3
    resp = client.post(reverse("accounts:signup"), {"email": "New@Example.com"})
    assert resp.url == reverse("accounts:check_email")

    resp = client.get(reverse("accounts:check_email"))
    assert b"Check your inbox" in resp.content
    assert b"new@example.com" in resp.content

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["new@example.com"]
    assert msg.alternatives and msg.alternatives[0][1] == "text/html"
    verify_path = path_of(link_from_mail(msg))

    resp = client.post(verify_path)
    assert resp.url == reverse("plans:today")

    user = User.objects.get(email="new@example.com")
    journey = Journey.objects.get(user=user)
    assert journey.current_level == 3
    block = journey.blocks.get()
    assert (block.index, block.level, block.status) == (1, 3, "active")
    assert [d.kind for d in block.days.all()] == ["run", "rest"]
    assert OnboardingStart.objects.get().user == user
    assert "onboarding" not in client.session

    resp = client.get(reverse("plans:today"))
    assert resp.status_code == 200


def test_link_opened_in_another_browser_still_attaches_answers(client):
    from django.test import Client

    answer_onboarding(client, "active", "yes")  # -> level 4
    client.post(reverse("accounts:signup"), {"email": "x@example.com"})
    other = Client()
    other.post(path_of(link_from_mail(mail.outbox[0])))
    assert Journey.objects.get(user__email="x@example.com").current_level == 4


def test_returning_user_login_keeps_existing_journey(client):
    answer_onboarding(client)
    client.post(reverse("accounts:signup"), {"email": "x@example.com"})
    client.post(path_of(link_from_mail(mail.outbox[0])))
    client.post(reverse("accounts:logout"))

    client.post(reverse("accounts:login"), {"email": "x@example.com"})
    client.post(latest_link())
    assert Journey.objects.count() == 1
    assert client.get(reverse("plans:today")).status_code == 200


def test_login_without_onboarding_goes_to_start(client):
    client.post(reverse("accounts:login"), {"email": "x@example.com"})
    resp = client.post(path_of(link_from_mail(mail.outbox[0])))
    assert resp.url == reverse("plans:start")
    answer_onboarding(client, "sitting", "yes")
    assert client.get(reverse("plans:today")).status_code == 200
    assert Journey.objects.get().current_level == 2


def test_session_lasts_60_days(client, settings):
    assert settings.SESSION_COOKIE_AGE == 60 * 24 * 60 * 60


def test_logout_requires_post(client):
    user = make_user()
    client.force_login(user)
    assert client.get(reverse("accounts:logout")).status_code == 405
    client.post(reverse("accounts:logout"))
    assert client.get(reverse("plans:today")).status_code == 302


def test_signup_requires_onboarding(client):
    resp = client.post(reverse("accounts:signup"), {"email": "x@example.com"})
    assert resp.url == reverse("plans:start")
    assert not mail.outbox
