from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from plans import messages, services
from plans.models import Block, DayLog, Journey

from .factories import make_journey, make_user

pytestmark = pytest.mark.django_db


def run_day(journey):
    return DayLog.objects.get(block__journey=journey, block__status="active", kind="run")


def rest_day(journey):
    return DayLog.objects.get(block__journey=journey, block__status="active", kind="rest")


def test_create_journey_is_idempotent():
    user = make_user()
    j1 = services.create_journey(user, "walks", "maybe")
    j2 = services.create_journey(user, "active", "yes")
    assert j1.pk == j2.pk
    assert Block.objects.count() == 1


def test_first_completion_uses_first_ever_message():
    journey = make_journey()
    result = services.complete_day(run_day(journey))
    assert result.message in messages.MESSAGES["first_ever"]
    assert not result.block_done
    journey.refresh_from_db()
    assert journey.last_message_key.startswith("first_ever:")


def test_completion_is_idempotent():
    journey = make_journey()
    day = run_day(journey)
    first = services.complete_day(day)
    again = services.complete_day(day)
    assert again.already_done
    assert again.message == first.message


def test_rest_day_message_and_block_done():
    journey = make_journey()
    services.complete_day(run_day(journey))
    result = services.complete_day(rest_day(journey))
    assert result.message in messages.MESSAGES["rest"]
    assert result.block_done


def _second_block(journey, level, now):
    """Simulate block 1 done and block 2 active at `level` (feedback lands in phase 3)."""
    Block.objects.filter(journey=journey).update(status="completed")
    return services.create_block(journey, index=2, level=level, unlocks_at=now, status="active", started_at=now)


def test_longest_jog_message_uses_minutes():
    now = timezone.now()
    journey = make_journey(activity="walks", jog="maybe", now=now)  # level 2: 1 min
    services.complete_day(run_day(journey), now=now)
    _second_block(journey, level=3, now=now)  # 2 min continuous: new longest
    result = services.complete_day(run_day(journey), now=now + timedelta(days=2))
    templates = [t.format(minutes=2) for t in messages.MESSAGES["harder_level"]]
    assert result.message in templates


def test_same_length_jog_uses_standard_message():
    now = timezone.now()
    journey = make_journey(activity="sitting", jog="maybe", now=now)  # level 1
    services.complete_day(run_day(journey), now=now)
    _second_block(journey, level=2, now=now)  # still 1 min continuous
    result = services.complete_day(run_day(journey), now=now + timedelta(days=2))
    assert result.message in messages.MESSAGES["standard"]


def test_completion_after_gap_uses_after_gap_message():
    now = timezone.now()
    journey = make_journey(now=now)
    services.complete_day(run_day(journey), now=now)
    result = services.complete_day(rest_day(journey), now=now + timedelta(days=6))
    # Rest days keep their own group even after a gap; check a run after a gap:
    assert result.message in messages.MESSAGES["rest"]
    _second_block(journey, level=journey.current_level, now=now)
    result = services.complete_day(run_day(journey), now=now + timedelta(days=13))
    assert result.message in messages.MESSAGES["after_gap"]


# --- Views -----------------------------------------------------------------------------

def test_today_requires_login(client):
    resp = client.get(reverse("plans:today"))
    assert resp.status_code == 302
    assert reverse("accounts:login") in resp.url


def test_today_shows_both_days(client):
    journey = make_journey()
    client.force_login(journey.user)
    resp = client.get(reverse("plans:today"))
    body = resp.content.decode()
    assert "Day 1 · Run" in body and "Day 2 · Rest" in body
    assert "Talk test" in body and "Walking is always allowed" in body
    assert "Block 1" in body and "of about" in body
    assert body.count("data-complete-form") == 2


def test_complete_day_json(client):
    journey = make_journey()
    client.force_login(journey.user)
    day = run_day(journey)
    resp = client.post(reverse("plans:complete_day", args=[day.pk]), HTTP_ACCEPT="application/json")
    data = resp.json()
    assert data["ok"] and data["message"] and not data["already_done"] and not data["block_done"]
    day.refresh_from_db()
    assert day.completed_at is not None


def test_complete_day_form_fallback_redirects_with_message(client):
    journey = make_journey()
    client.force_login(journey.user)
    resp = client.post(reverse("plans:complete_day", args=[run_day(journey).pk]), follow=True)
    assert resp.redirect_chain[-1][0] == reverse("plans:today")
    assert "Done" in resp.content.decode()
    assert any(m.message for m in resp.context["messages"])


def test_cannot_complete_someone_elses_day(client):
    journey = make_journey()
    intruder = make_user("intruder@example.com")
    client.force_login(intruder)
    resp = client.post(reverse("plans:complete_day", args=[run_day(journey).pk]))
    assert resp.status_code == 404
    assert run_day(journey).completed_at is None


def test_complete_day_requires_post(client):
    journey = make_journey()
    client.force_login(journey.user)
    assert client.get(reverse("plans:complete_day", args=[run_day(journey).pk])).status_code == 405


def test_compliment_html_is_escaped(client):
    journey = make_journey()
    day = run_day(journey)
    DayLog.objects.filter(pk=day.pk).update(completed_at=timezone.now(), compliment="<script>x</script>")
    client.force_login(journey.user)
    body = client.get(reverse("plans:today")).content.decode()
    assert "<script>x</script>" not in body
    assert "&lt;script&gt;" in body


def test_logged_in_landing_redirects_to_today(client):
    journey = make_journey()
    client.force_login(journey.user)
    assert client.get("/").url == reverse("plans:today")


def test_journey_lookup_scoped_to_user():
    make_journey()
    other = make_user("b@example.com")
    assert not Journey.objects.filter(user=other).exists()
