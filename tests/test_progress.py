import pytest
from django.urls import reverse

from plans import charts, engine, fuel, learn, services

from .factories import make_journey

pytestmark = pytest.mark.django_db


def test_every_level_has_a_lesson():
    for level in range(1, 13):
        lesson = learn.lesson_for("run", level)
        assert lesson["term"] and lesson["meaning"] and lesson["benefit"]
    assert learn.lesson_for("rest", 5) is learn.REST_LESSON


def test_fuel_tip_rotates_and_has_two_distinct_ideas():
    tips = [fuel.fuel_tip(i) for i in range(6)]
    assert all(t["before"][0] != t["before"][1] for t in tips)
    assert len({t["after"] for t in tips}) > 1
    assert "doctor" in tips[0]["note"]


def test_total_jog_minutes():
    assert engine.total_jog_minutes(1) == 6
    assert engine.total_jog_minutes(2) == 8
    assert engine.total_jog_minutes(10) == 20
    assert engine.total_jog_minutes(12) == 30


def test_chart_geometry():
    assert charts.bar_chart([]) is None
    pts = [{"label": str(i), "value": v, "tooltip": f"t{i}"} for i, v in enumerate([6, 8, 10, 8], start=1)]
    c = charts.bar_chart(pts)
    assert len(c["bars"]) == 4
    assert [g["label"] for g in c["grid"]] == [0, 5, 10]
    tallest = min(b["cap_y"] for b in c["bars"])
    assert c["bars"][2]["cap_y"] == tallest
    # Only the best and the latest get value labels.
    assert [b["show_value"] for b in c["bars"]] == [False, False, True, True]
    assert all(b["path"].startswith("M") for b in c["bars"])


def test_chart_bars_capped_at_24px():
    c = charts.bar_chart([{"label": "1", "value": 5, "tooltip": ""}])
    path = c["bars"][0]["path"]
    xs = [float(tok.split(",")[0].lstrip("MVHQ")) for tok in path.replace("Q", " Q").split() if "," in tok]
    assert max(xs) - min(xs) <= 24.01


def test_progress_stats_and_page(client):
    journey = make_journey()
    for day in journey.blocks.get().days.all():
        services.complete_day(day)
    stats = services.progress_stats(journey)
    assert stats["run_count"] == 1 and stats["rest_days"] == 1
    assert stats["total_jog_minutes"] == 8 and stats["longest_jog"] == 1
    client.force_login(journey.user)
    body = client.get(reverse("plans:progress")).content.decode()
    assert "Minutes of jogging, run by run" in body and "<svg" in body
    assert "Show as a table" in body
    assert "streak" not in body.lower()


def test_progress_empty_state(client):
    journey = make_journey()
    client.force_login(journey.user)
    body = client.get(reverse("plans:progress")).content.decode()
    assert "Your chart starts with your first run" in body
