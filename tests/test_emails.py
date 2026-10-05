from datetime import datetime, timedelta, timezone as dt_tz

import pytest
from django.core import mail
from django.core.management import call_command
from django.urls import reverse

from notifications import email as mailer
from notifications import scheduler
from notifications.models import EmailLog
from plans import engine, services
from plans.models import Block

from .factories import make_journey, make_user

pytestmark = pytest.mark.django_db

# A Wednesday, 10:00 UTC. Users in these tests live in UTC so the 08–20 window is easy to reason about.
WED = datetime(2026, 10, 7, 10, 0, tzinfo=dt_tz.utc)
SUN_EVENING = datetime(2026, 10, 11, 18, 0, tzinfo=dt_tz.utc)


def journey_at(now, **kw):
    user = make_user(timezone="UTC")
    return make_journey(user, now=now, **kw)


def locked_next_block(journey, finished_at):
    block = journey.blocks.get(status="active")
    for d in block.days.all():
        services.complete_day(d, now=finished_at)
    return services.submit_feedback(block, engine.JUST_RIGHT, now=finished_at).next_block


def kinds():
    return list(EmailLog.objects.values_list("kind", flat=True))


# --- next_block ----------------------------------------------------------------------

def test_next_block_email_when_unlocked_and_unopened():
    t0 = WED - timedelta(days=3)
    journey = journey_at(t0)
    nxt = locked_next_block(journey, t0)
    assert nxt.unlocks_at <= WED
    counts = scheduler.run(now=WED)
    assert counts == {"next_block": 1}
    msg = mail.outbox[-1]
    assert msg.to == [journey.user.email]
    assert "/today/" in msg.body
    assert msg.extra_headers["List-Unsubscribe"].startswith("<http")
    assert msg.extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert msg.alternatives[0][1] == "text/html"


def test_scheduler_is_idempotent():
    t0 = WED - timedelta(days=3)
    journey = journey_at(t0)
    locked_next_block(journey, t0)
    scheduler.run(now=WED)
    scheduler.run(now=WED + timedelta(hours=1))
    scheduler.run(now=WED + timedelta(days=1))
    assert kinds().count("next_block") == 1


def test_no_next_block_email_before_unlock():
    t0 = WED - timedelta(hours=5)
    journey = journey_at(t0)
    locked_next_block(journey, t0)
    assert scheduler.run(now=WED) == {}


def test_no_next_block_email_once_opened():
    t0 = WED - timedelta(days=3)
    journey = journey_at(t0)
    locked_next_block(journey, t0)
    services.refresh(journey, now=WED - timedelta(hours=1))  # user opened the app
    assert scheduler.run(now=WED) == {}


# --- send window, subscription -----------------------------------------------------------

def test_respects_local_send_window():
    t0 = WED - timedelta(days=3)
    journey = journey_at(t0)
    locked_next_block(journey, t0)
    assert scheduler.run(now=WED.replace(hour=22)) == {}
    assert scheduler.run(now=WED.replace(hour=7)) == {}


def test_send_window_uses_user_timezone():
    t0 = WED - timedelta(days=3)
    journey = journey_at(t0)
    journey.user.timezone = "Asia/Kolkata"  # UTC 22:00 = 03:30 IST; UTC 04:00 = 09:30 IST
    journey.user.save()
    locked_next_block(journey, t0)
    assert scheduler.run(now=WED.replace(hour=22)) == {}
    assert scheduler.run(now=WED.replace(hour=4)) == {"next_block": 1}


def test_unsubscribed_users_get_nothing():
    t0 = WED - timedelta(days=3)
    journey = journey_at(t0)
    journey.user.is_subscribed = False
    journey.user.save()
    locked_next_block(journey, t0)
    assert scheduler.run(now=WED) == {}
    assert not mail.outbox


# --- nudge & door open --------------------------------------------------------------------

def test_nudge_after_three_idle_days_once_per_block():
    journey = journey_at(WED - timedelta(days=3, hours=1))  # block 1 unlocked at creation
    assert scheduler.run(now=WED) == {"nudge": 1}
    assert mail.outbox[-1].subject in scheduler.NUDGE_SUBJECTS
    assert scheduler.run(now=WED + timedelta(days=2)) == {}


def test_no_nudge_if_something_completed():
    t0 = WED - timedelta(days=4)
    journey = journey_at(t0)
    services.complete_day(journey.blocks.get().days.get(kind="run"), now=t0 + timedelta(hours=1))
    assert scheduler.run(now=WED) == {}


def test_door_open_after_14_days_then_silence_until_return():
    t0 = WED - timedelta(days=15)
    journey = journey_at(t0)
    assert scheduler.run(now=WED) == {"door_open": 1}
    assert mail.outbox[-1].subject == "We'll leave the door open"
    # Weeks later: still nothing.
    assert scheduler.run(now=WED + timedelta(days=10)) == {}
    assert scheduler.run(now=SUN_EVENING + timedelta(days=14)) == {}
    # They come back and do something: emails can resume (e.g. weekly progress).
    back = WED + timedelta(days=14)  # Wed 21 Oct, inside the week before Sun 25 Oct
    block = services.refresh(journey, now=back).block
    services.complete_day(block.days.get(kind="run"), now=back)
    assert scheduler.run(now=datetime(2026, 10, 25, 18, 0, tzinfo=dt_tz.utc)) == {"weekly_progress": 1}


def test_min_spacing_between_emails():
    journey = journey_at(WED - timedelta(days=3, hours=1))
    EmailLog.objects.create(user=journey.user, kind="welcome", sent_at=WED - timedelta(hours=2))
    assert scheduler.run(now=WED) == {}


# --- weekly progress ------------------------------------------------------------------------

def test_weekly_progress_on_sunday_evening_with_chart():
    t0 = SUN_EVENING - timedelta(days=2)
    journey = journey_at(t0)
    for d in journey.blocks.get().days.all():
        services.complete_day(d, now=t0)
    assert scheduler.run(now=SUN_EVENING) == {"weekly_progress": 1}
    msg = mail.outbox[-1]
    html = msg.alternatives[0][0]
    assert "This week" in msg.body and "Run 1: 8 min" in msg.body
    assert 'bgcolor="#C2410C"' in html  # the latest bar
    assert "<svg" not in html and "<script" not in html
    assert scheduler.run(now=SUN_EVENING + timedelta(hours=1)) == {}


def test_no_weekly_progress_without_recent_activity():
    t0 = SUN_EVENING - timedelta(days=9)
    journey = journey_at(t0)
    services.complete_day(journey.blocks.get().days.get(kind="run"), now=t0)
    # Run 9 days ago; block is a week+ idle, so a nudge is due instead, not the weekly email.
    assert "weekly_progress" not in scheduler.run(now=SUN_EVENING)


def test_no_weekly_on_other_days():
    t0 = WED - timedelta(days=1)
    journey = journey_at(t0)
    for d in journey.blocks.get().days.all():
        services.complete_day(d, now=t0)
    assert "weekly_progress" not in scheduler.run(now=WED)


def test_completed_journeys_get_no_scheduled_email():
    t0 = WED - timedelta(days=20)
    journey = journey_at(t0)
    journey.completed_at = t0
    journey.save()
    assert scheduler.run(now=WED) == {}


# --- plumbing -------------------------------------------------------------------------------

def test_failed_send_releases_claim(monkeypatch):
    user = make_user()

    def boom(*a, **k):
        raise ConnectionError("SMTP down")

    monkeypatch.setattr(mailer, "send", boom)
    assert mailer.send_to_user(user, "nudge", "s", "nudge", ref="x") is False
    assert not EmailLog.objects.exists()


def test_email_chart_scales_and_caps_bars():
    runs = [{"number": i, "jog_minutes": m} for i, m in enumerate([6, 8, 10, 12, 16, 15, 15, 16, 20, 24, 20, 25], 1)]
    chart = mailer.email_chart(runs)
    assert len(chart["bars"]) == mailer.EMAIL_CHART_MAX_BARS
    assert chart["bars"][0]["number"] == 3
    assert max(b["height"] for b in chart["bars"]) == mailer.EMAIL_CHART_HEIGHT
    assert chart["bars"][-1]["is_latest"]
    assert mailer.email_chart([]) is None


def test_management_command(capsys):
    call_command("send_scheduled_emails")
    assert "Sent 0 email(s)" in capsys.readouterr().out


def test_welcome_email_sent_once_on_signup(client):
    from .factories import answer_onboarding
    from .test_auth import latest_link

    answer_onboarding(client)
    client.post(reverse("accounts:signup"), {"email": "w@example.com"})
    client.post(latest_link())
    welcome = [m for m in mail.outbox if "Welcome" in m.subject]
    assert len(welcome) == 1
    assert "You just did the hardest part" in welcome[0].body
    assert "/unsubscribe/" in welcome[0].body
    assert EmailLog.objects.filter(kind="welcome").count() == 1


def test_magic_links_still_sent_when_unsubscribed(client):
    user = make_user("u@example.com", is_subscribed=False)
    client.post(reverse("accounts:login"), {"email": user.email})
    assert len(mail.outbox) == 1
