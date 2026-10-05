"""Block lifecycle: feedback -> locked next block -> unlock -> gap rules -> milestones -> finish."""

from datetime import timedelta, timezone as dt_timezone

import pytest
from django.urls import reverse
from django.utils import timezone

from plans import engine, messages, services
from plans.models import Block, DayLog, Journey, Milestone

from .factories import make_journey, make_user

pytestmark = pytest.mark.django_db
T0 = timezone.now().replace(microsecond=0)


def active(journey):
    return journey.blocks.get(status="active")


def finish_block(journey, feedback, now):
    """Complete both days of the active block, then give feedback."""
    block = active(journey)
    for day in block.days.all():
        services.complete_day(day, now=now)
    return services.submit_feedback(block, feedback, now=now)


def unlock(journey, now):
    return services.refresh(journey, now=now)


# --- Feedback -> next block --------------------------------------------------------

def test_feedback_creates_locked_next_block_with_unlock_time():
    journey = make_journey(now=T0)  # walks+maybe -> level 2
    result = finish_block(journey, engine.JUST_RIGHT, T0 + timedelta(hours=20))
    nxt = result.next_block
    assert (nxt.index, nxt.level, nxt.status) == (2, 3, "locked")
    assert nxt.unlocks_at == T0 + timedelta(days=2)  # 2 days after start beats "finished at"
    assert [d.kind for d in nxt.days.all()] == ["run", "rest"]
    assert result.message in messages.MESSAGES["feedback_just_right"]

    block1 = journey.blocks.get(index=1)
    assert (block1.status, block1.feedback) == ("completed", "just_right")
    journey.refresh_from_db()
    assert journey.blocks_completed == 1


def test_late_finish_unlocks_immediately():
    journey = make_journey(now=T0)
    finished_at = T0 + timedelta(days=3)
    result = finish_block(journey, engine.JUST_RIGHT, finished_at)
    assert result.next_block.unlocks_at == finished_at


def test_min_gap_is_a_setting(settings):
    settings.BLOCK_MIN_GAP_DAYS = 1
    journey = make_journey(now=T0)
    result = finish_block(journey, engine.JUST_RIGHT, T0 + timedelta(hours=2))
    assert result.next_block.unlocks_at == T0 + timedelta(days=1)


def test_too_easy_twice_jumps_two_levels():
    journey = make_journey(now=T0)  # level 2
    finish_block(journey, engine.TOO_EASY, T0)
    unlock(journey, T0 + timedelta(days=2))
    assert active(journey).level == 3
    result = finish_block(journey, engine.TOO_EASY, T0 + timedelta(days=2, hours=1))
    assert result.next_block.level == 5


def test_too_hard_twice_steps_down():
    journey = make_journey(activity="active", jog="yes", now=T0)  # level 4
    finish_block(journey, engine.TOO_HARD, T0)
    unlock(journey, T0 + timedelta(days=2))
    assert active(journey).level == 4
    result = finish_block(journey, engine.TOO_HARD, T0 + timedelta(days=2, hours=1))
    assert result.next_block.level == 3


def test_didnt_do_skips_and_repeats_without_counting():
    journey = make_journey(now=T0)
    block = active(journey)
    result = services.submit_feedback(block, engine.DIDNT_DO, now=T0 + timedelta(hours=1))
    block.refresh_from_db()
    assert block.status == "skipped"
    assert result.next_block.level == block.level
    journey.refresh_from_db()
    assert journey.blocks_completed == 0
    assert not Milestone.objects.exists()


def test_feedback_twice_is_harmless():
    journey = make_journey(now=T0)
    block = active(journey)
    services.submit_feedback(block, engine.JUST_RIGHT, now=T0)
    again = services.submit_feedback(block, engine.TOO_HARD, now=T0)
    assert again.message == ""
    assert Block.objects.count() == 2
    block.refresh_from_db()
    assert block.feedback == "just_right"


def test_unknown_feedback_rejected():
    journey = make_journey(now=T0)
    with pytest.raises(ValueError):
        services.submit_feedback(active(journey), "meh")


# --- Unlocking --------------------------------------------------------------------------

def test_locked_block_stays_locked_until_due():
    journey = make_journey(now=T0)
    finish_block(journey, engine.JUST_RIGHT, T0)
    r = unlock(journey, T0 + timedelta(days=1))
    assert r.block.status == "locked" and r.message == ""


def test_due_block_unlocks_normally():
    journey = make_journey(now=T0)
    finish_block(journey, engine.JUST_RIGHT, T0)
    r = unlock(journey, T0 + timedelta(days=3))
    assert r.block.status == "active"
    assert r.block.started_at == T0 + timedelta(days=3)
    assert r.message == "" and r.block.entry_note == ""
    journey.refresh_from_db()
    assert journey.current_level == 3


def test_skip_wait_unlocks_early():
    journey = make_journey(now=T0)
    finish_block(journey, engine.JUST_RIGHT, T0)
    assert services.refresh(journey, now=T0 + timedelta(hours=1), skip_wait=True).block.status == "active"


# --- Gap rules ------------------------------------------------------------------------------

def test_welcome_back_after_5_days_repeats_previous_level():
    journey = make_journey(now=T0)  # level 2
    finish_block(journey, engine.JUST_RIGHT, T0)  # planned level 3, unlocks T0+2d
    r = unlock(journey, T0 + timedelta(days=8))  # 6 days after unlock
    assert r.block.level == 2
    assert r.block.entry_note == engine.GAP_WELCOME_BACK
    assert r.message in messages.MESSAGES["welcome_back"]
    assert [d.kind for d in r.block.days.all()] == ["run", "rest"]


def test_gap_counted_from_unlock_not_feedback():
    journey = make_journey(now=T0)
    finish_block(journey, engine.JUST_RIGHT, T0)  # unlocks T0+2d
    r = unlock(journey, T0 + timedelta(days=6))  # 4 days after unlock: normal
    assert r.block.level == 3 and r.message == ""


def test_ease_down_after_14_days():
    journey = make_journey(activity="active", jog="yes", now=T0)  # level 4
    finish_block(journey, engine.JUST_RIGHT, T0)  # planned 5
    r = unlock(journey, T0 + timedelta(days=2 + 15))
    assert r.block.level == 3  # previous level 4 minus one
    assert r.message in messages.MESSAGES["ease_down"]


def test_ease_down_never_below_level_one():
    journey = make_journey(activity="sitting", jog="not_yet", now=T0)  # level 1
    finish_block(journey, engine.TOO_HARD, T0)
    assert unlock(journey, T0 + timedelta(days=30)).block.level == 1


def test_untouched_active_block_eases_down_once():
    journey = make_journey(activity="active", jog="yes", now=T0)  # level 4, nothing done
    r = unlock(journey, T0 + timedelta(days=15))
    assert r.block.level == 3 and r.message
    again = unlock(journey, T0 + timedelta(days=15, hours=1))
    assert again.block.level == 3 and again.message == ""


def test_active_block_with_progress_is_not_rebuilt():
    journey = make_journey(activity="active", jog="yes", now=T0)
    services.complete_day(active(journey).days.get(kind="run"), now=T0)
    r = unlock(journey, T0 + timedelta(days=20))
    assert r.block.level == 4 and r.message
    assert r.block.days.filter(completed_at__isnull=False).count() == 1


# --- Milestones ------------------------------------------------------------------------------

def test_first_block_milestone_awarded_once():
    journey = make_journey(now=T0)
    result = finish_block(journey, engine.JUST_RIGHT, T0)
    assert result.milestones == [engine.MILESTONE_FIRST_BLOCK]
    unlock(journey, T0 + timedelta(days=2))
    result = finish_block(journey, engine.JUST_RIGHT, T0 + timedelta(days=2))
    assert engine.MILESTONE_FIRST_BLOCK not in result.milestones
    assert Milestone.objects.filter(key="first_block").count() == 1


def test_halfway_when_next_block_reaches_level_six():
    user = make_user()
    journey = services.create_journey(user, "active", "yes", now=T0)  # level 4
    journey.blocks.update(level=5)
    result = finish_block(journey, engine.JUST_RIGHT, T0)
    assert engine.MILESTONE_HALFWAY in result.milestones


def test_five_minutes_on_completing_level_six_run():
    journey = make_journey(now=T0)
    journey.blocks.update(level=6)
    result = services.complete_day(active(journey).days.get(kind="run"), now=T0)
    assert result.milestones == [engine.MILESTONE_FIVE_MINUTES]


def test_finishing_level_twelve_completes_journey():
    journey = make_journey(now=T0)
    journey.blocks.update(level=12)
    result = finish_block(journey, engine.JUST_RIGHT, T0)
    assert result.journey_complete and result.next_block is None
    journey.refresh_from_db()
    assert journey.completed_at is not None
    assert set(journey.milestones.values_list("key", flat=True)) >= {"five_k", "five_minutes", "first_block"}


# --- Views -------------------------------------------------------------------------------------

@pytest.fixture
def logged_in(client):
    journey = make_journey()
    client.force_login(journey.user)
    return client, journey


def test_feedback_form_appears_when_both_days_done(logged_in):
    client, journey = logged_in
    body = client.get(reverse("plans:today")).content.decode()
    assert "I&#x27;m done with this block" in body or "I'm done with this block" in body
    for day in active(journey).days.all():
        services.complete_day(day)
    body = client.get(reverse("plans:today")).content.decode()
    assert "How did it feel?" in body and "data-block-done hidden" not in body


def test_feedback_post_redirects_to_milestone_then_waiting(logged_in):
    client, journey = logged_in
    block = active(journey)
    resp = client.post(reverse("plans:block_feedback", args=[block.pk]), {"feedback": "just_right"})
    assert resp.url == reverse("plans:milestone", args=["first_block"])
    resp = client.get(resp.url)
    assert resp.status_code == 200 and b"First block done!" in resp.content
    assert Milestone.objects.get().seen_at is not None
    resp = client.get(reverse("plans:today"))
    assert b"Rest up" in resp.content and b"Add to calendar" in resp.content


def test_feedback_json(logged_in):
    client, journey = logged_in
    resp = client.post(reverse("plans:block_feedback", args=[active(journey).pk]),
                       {"feedback": "too_hard"}, HTTP_ACCEPT="application/json")
    data = resp.json()
    assert data["ok"] and data["message"] in messages.MESSAGES["feedback_too_hard"]
    assert data["redirect"] == reverse("plans:milestone", args=["first_block"])


def test_cannot_give_feedback_on_others_block(logged_in):
    client, _ = logged_in
    other = make_journey(make_user("other@example.com"))
    resp = client.post(reverse("plans:block_feedback", args=[active(other).pk]), {"feedback": "too_easy"})
    assert resp.status_code == 404


def test_skip_wait_only_in_debug(logged_in, settings):
    client, journey = logged_in
    services.submit_feedback(active(journey), "just_right")
    settings.DEBUG = False
    assert b"Rest up" in client.get(reverse("plans:today") + "?skip_wait=1").content
    settings.DEBUG = True
    assert b"Your next 2 days" in client.get(reverse("plans:today") + "?skip_wait=1").content


def test_ics_download(logged_in):
    client, journey = logged_in
    services.submit_feedback(active(journey), "just_right")
    resp = client.get(reverse("plans:next_block_ics"))
    assert resp["Content-Type"].startswith("text/calendar")
    body = resp.content.decode()
    assert body.startswith("BEGIN:VCALENDAR\r\n") and "BEGIN:VEVENT" in body and body.endswith("END:VCALENDAR\r\n")
    nxt = journey.blocks.get(status="locked")
    assert f"DTSTART:{nxt.unlocks_at.astimezone(dt_timezone.utc):%Y%m%dT%H%M%SZ}" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))


def test_ics_404_without_locked_block(logged_in):
    client, _ = logged_in
    assert client.get(reverse("plans:next_block_ics")).status_code == 404


def test_milestone_page_requires_earning_it(logged_in):
    client, _ = logged_in
    assert client.get(reverse("plans:milestone", args=["five_k"])).status_code == 404
    assert client.get(reverse("plans:milestone", args=["bogus"])).status_code == 404


def test_finished_flow(logged_in):
    client, journey = logged_in
    journey.blocks.update(level=12)
    finish_block(journey, "just_right", timezone.now())
    Milestone.objects.update(seen_at=timezone.now())
    assert client.get(reverse("plans:today")).url == reverse("plans:finished")
    body = client.get(reverse("plans:finished")).content.decode()
    assert "parkrun" in body and "10K" in body


def test_welcome_back_flash_shown_once(logged_in):
    client, journey = logged_in
    journey.last_activity_at = timezone.now() - timedelta(days=7)
    journey.save()
    journey.blocks.update(started_at=timezone.now() - timedelta(days=7))
    resp = client.get(reverse("plans:today"))
    assert any(m.message in messages.MESSAGES["welcome_back"] for m in resp.context["messages"])
    resp = client.get(reverse("plans:today"))
    assert not list(resp.context["messages"])


def test_run_day_shows_lesson_and_fuel(logged_in):
    client, _ = logged_in
    body = client.get(reverse("plans:today")).content.decode()
    assert "Running word:" in body and "Aerobic base" in body  # level 2
    assert "Fuel ideas" in body and "Recovery &amp; adaptation" in body


def test_older_runner_waits_three_days():
    journey = make_journey(now=T0, age="65_plus")
    result = finish_block(journey, engine.JUST_RIGHT, T0 + timedelta(hours=2))
    assert result.next_block.unlocks_at == T0 + timedelta(days=3)


def test_age_group_stored_on_journey_from_signup(client):
    from django.core import mail
    from .factories import answer_onboarding
    from .test_auth import link_from_mail, path_of

    answer_onboarding(client, "active", "yes", age="55_64")
    client.post(reverse("accounts:signup"), {"email": "older@example.com"})
    client.post(path_of(link_from_mail(mail.outbox[0])))
    journey = Journey.objects.get(user__email="older@example.com")
    assert journey.age_group == "55_64" and journey.current_level == 2
