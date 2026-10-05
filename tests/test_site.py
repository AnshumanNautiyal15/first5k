from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from accounts import magic_link
from accounts.models import MagicLoginToken, User
from core import stats
from plans import engine, services
from plans.models import Journey, OnboardingStart

from .factories import make_journey, make_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("name,text", [
    ("core:privacy", "Privacy policy"),
    ("core:terms", "Terms of use"),
    ("core:health", "Health &amp; safety"),
])
def test_legal_pages(client, name, text):
    resp = client.get(reverse(name))
    assert resp.status_code == 200 and text in resp.content.decode()


def test_footer_links_and_safety_copy_everywhere(client):
    body = client.get("/").content.decode()
    for url in ("/privacy/", "/terms/", "/health/"):
        assert f'href="{url}"' in body
    assert "Not medical advice" in body


def test_seo_tags_on_landing(client):
    body = client.get("/").content.decode()
    assert '<meta name="description"' in body
    assert 'property="og:title"' in body and 'property="og:url"' in body


def test_analytics_off_by_default_and_on_with_env(client, settings):
    assert "plausible.io" not in client.get("/").content.decode()
    settings.PLAUSIBLE_DOMAIN = "first5k.app"
    assert 'data-domain="first5k.app"' in client.get("/").content.decode()


def test_robots_txt(client):
    body = client.get("/robots.txt").content.decode()
    assert "Disallow: /" in body and "Allow: /start/" in body


def test_custom_404(client, settings):
    settings.DEBUG = False
    resp = client.get("/definitely-not-here/")
    assert resp.status_code == 404 and b"We took a wrong turn" in resp.content


def test_500_template_renders_without_request_context():
    from django.template.loader import render_to_string

    assert "Something went wrong" in render_to_string("500.html")


# --- Admin funnel -------------------------------------------------------------------------

def test_funnel_counts():
    OnboardingStart.objects.bulk_create(OnboardingStart(session_key=str(i)) for i in range(10))
    j1 = make_journey(make_user("a@example.com"))
    make_journey(make_user("b@example.com"))
    services.submit_feedback(j1.blocks.get(), engine.JUST_RIGHT)
    services.refresh(j1, skip_wait=True)
    rows = stats.funnel()["rows"]
    assert [r["count"] for r in rows] == [10, 2, 1, 1, 0]
    assert rows[1]["of_prev"] == 20 and rows[2]["of_prev"] == 50


def test_funnel_excludes_staff_and_respects_period():
    staff = User.objects.create_superuser("admin@example.com", "pw")
    make_journey(staff)
    old = make_journey(make_user("old@example.com"))
    Journey.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=60))
    assert stats.funnel(30)["rows"][1]["count"] == 0
    assert stats.funnel(None)["rows"][1]["count"] == 1


def test_stats_page_staff_only(client):
    assert client.get("/admin/stats/").status_code == 302
    client.force_login(make_user("plain@example.com"))
    assert client.get("/admin/stats/").status_code == 302
    client.force_login(User.objects.create_superuser("admin@example.com", "pw"))
    resp = client.get("/admin/stats/?period=all")
    assert resp.status_code == 200 and b"Onboarding started" in resp.content
    assert b"Funnel stats" in client.get("/admin/").content


# --- Commands -----------------------------------------------------------------------------

def test_seed_demo_creates_every_stage(settings, capsys):
    settings.DEBUG = True
    call_command("seed_demo")
    out = capsys.readouterr().out
    assert out.count("/auth/verify/") == 7
    assert Journey.objects.filter(user__email__endswith="demo.first5k.test").count() == 7
    assert Journey.objects.get(user__email="finished@demo.first5k.test").is_complete
    call_command("seed_demo")  # re-runnable
    assert Journey.objects.filter(user__email__endswith="demo.first5k.test").count() == 7


def test_seed_demo_refuses_in_production(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_demo")


def test_old_login_tokens_purged_by_hourly_command():
    magic_link.issue_token("a@example.com", "1.1.1.1")
    magic_link.issue_token("b@example.com", "1.1.1.1")
    MagicLoginToken.objects.filter(email="a@example.com").update(created_at=timezone.now() - timedelta(days=31))
    call_command("send_scheduled_emails")
    assert list(MagicLoginToken.objects.values_list("email", flat=True)) == ["b@example.com"]
