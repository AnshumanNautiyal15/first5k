from datetime import datetime, timedelta, timezone

import pytest

from plans import engine as e

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


# --- Levels data ----------------------------------------------------------------

def test_twelve_levels_numbered_in_order():
    assert e.MAX_LEVEL == 12
    assert [lvl["number"] for lvl in e.LEVELS] == list(range(1, 13))


@pytest.mark.parametrize("lvl", e.LEVELS, ids=lambda l: str(l["number"]))
def test_every_level_has_copy_and_continuous_minutes(lvl):
    for key in ("title", "description", "tip"):
        assert lvl[key].strip()
    assert lvl["continuous_minutes"] > 0


def test_continuous_minutes_never_decrease():
    minutes = [lvl["continuous_minutes"] for lvl in e.LEVELS]
    assert minutes == sorted(minutes)


def test_get_level_clamps():
    assert e.get_level(0)["number"] == 1
    assert e.get_level(99)["number"] == 12


# --- Session text ----------------------------------------------------------------

def test_session_steps_include_warmup_and_cooldown():
    steps = e.session_steps(1)
    assert steps[0].startswith("Walk briskly for 5 minutes")
    assert steps[1] == "Jog for 1 minute, then walk for 2 minutes. Do this 6 times."
    assert steps[-1].startswith("Walk gently for 5 minutes")


def test_session_steps_seconds_and_continuous():
    assert "walk for 90 seconds" in e.session_steps(2)[1]
    assert e.session_steps(10)[1] == "Jog slowly for 20 minutes without stopping."
    assert "5 km" in e.session_steps(12)[1]


def test_session_summary_and_total():
    assert e.session_summary(1) == "Jog 1 minute / walk 2 minutes × 6"
    assert e.session_total_minutes(1) == 28  # 5 + 18 + 5
    assert e.session_total_minutes(2) == 30  # 5 + 20 + 5
    assert e.session_total_minutes(12) is None


# --- Block layout -----------------------------------------------------------------

def test_default_block_layout_is_run_then_rest():
    for level in range(1, 13):
        assert e.block_layout(level) == ("run", "rest")


def test_block_layout_override(monkeypatch):
    monkeypatch.setitem(e.BLOCK_LAYOUT_OVERRIDES, 11, ("run", "run"))
    assert e.block_layout(11) == ("run", "run")
    assert e.block_layout(10) == ("run", "rest")


# --- Starting level ----------------------------------------------------------------

@pytest.mark.parametrize(
    "activity,jog,expected",
    [
        ("sitting", "not_yet", 1), ("sitting", "maybe", 1), ("sitting", "yes", 2),
        ("walks", "not_yet", 1), ("walks", "maybe", 2), ("walks", "yes", 3),
        ("active", "not_yet", 2), ("active", "maybe", 3), ("active", "yes", 4),
    ],
)
def test_start_level_mapping(activity, jog, expected):
    assert e.start_level(activity, jog) == expected


def test_start_level_unknown_answers_default_to_one():
    assert e.start_level("couch", "never") == 1


def test_all_choice_values_are_mapped():
    for a, _ in e.ACTIVITY_CHOICES:
        for j, _ in e.JOG_CHOICES:
            assert (a, j) in e._START_LEVELS


# --- Progression ---------------------------------------------------------------------

def test_just_right_goes_up_one():
    assert e.next_level(3, e.JUST_RIGHT) == e.NextStep(4)


def test_too_easy_once_goes_up_one():
    assert e.next_level(3, e.TOO_EASY, previous_feedback=e.JUST_RIGHT).level == 4
    assert e.next_level(3, e.TOO_EASY, previous_feedback=None).level == 4


def test_too_easy_twice_goes_up_two():
    assert e.next_level(3, e.TOO_EASY, previous_feedback=e.TOO_EASY).level == 5


def test_too_hard_once_repeats():
    assert e.next_level(5, e.TOO_HARD, previous_feedback=e.JUST_RIGHT).level == 5


def test_too_hard_twice_goes_down_one():
    assert e.next_level(5, e.TOO_HARD, previous_feedback=e.TOO_HARD).level == 4


def test_too_hard_twice_never_below_one():
    assert e.next_level(1, e.TOO_HARD, previous_feedback=e.TOO_HARD).level == 1


def test_didnt_do_repeats():
    assert e.next_level(7, e.DIDNT_DO, previous_feedback=e.TOO_HARD).level == 7


def test_levels_capped_at_twelve():
    assert e.next_level(11, e.TOO_EASY, previous_feedback=e.TOO_EASY) == e.NextStep(12)


@pytest.mark.parametrize("feedback", [e.TOO_EASY, e.JUST_RIGHT])
def test_finishing_level_twelve_completes_journey(feedback):
    assert e.next_level(12, feedback) == e.NextStep(12, journey_complete=True)


@pytest.mark.parametrize("feedback", [e.TOO_HARD, e.DIDNT_DO])
def test_struggling_at_level_twelve_repeats(feedback):
    assert e.next_level(12, feedback) == e.NextStep(12, journey_complete=False)


# --- Gap rules ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "days,expected",
    [
        (0, e.GAP_NORMAL),
        (4, e.GAP_NORMAL),
        (4.9, e.GAP_NORMAL),
        (5, e.GAP_WELCOME_BACK),
        (13, e.GAP_WELCOME_BACK),
        (13.9, e.GAP_WELCOME_BACK),
        (14, e.GAP_EASE_DOWN),
        (60, e.GAP_EASE_DOWN),
    ],
)
def test_gap_kind(days, expected):
    assert e.gap_kind(NOW - timedelta(days=days), NOW) == expected


def test_level_after_gap():
    assert e.level_after_gap(5, e.GAP_NORMAL) == 5
    assert e.level_after_gap(5, e.GAP_WELCOME_BACK) == 5
    assert e.level_after_gap(5, e.GAP_EASE_DOWN) == 4
    assert e.level_after_gap(1, e.GAP_EASE_DOWN) == 1


# --- Unlock timing -----------------------------------------------------------------

def test_unlock_waits_min_gap_after_start_when_finished_early():
    started = NOW
    finished = NOW + timedelta(hours=20)
    assert e.unlock_time(started, finished, 2) == NOW + timedelta(days=2)


def test_unlock_is_immediate_when_finished_late():
    started = NOW
    finished = NOW + timedelta(days=3)
    assert e.unlock_time(started, finished, 2) == finished


# --- Milestones --------------------------------------------------------------------

def test_milestones_after_run():
    assert e.milestones_after_run(5) == set()
    assert e.milestones_after_run(6) == {e.MILESTONE_FIVE_MINUTES}
    assert e.milestones_after_run(12) == {e.MILESTONE_FIVE_MINUTES, e.MILESTONE_FIVE_K}


def test_milestones_after_block():
    assert e.milestones_after_block(0, 2) == set()
    assert e.milestones_after_block(1, 2) == {e.MILESTONE_FIRST_BLOCK}
    assert e.milestones_after_block(5, 6) == {e.MILESTONE_FIRST_BLOCK, e.MILESTONE_HALFWAY}
    assert e.milestones_after_block(5, None) == {e.MILESTONE_FIRST_BLOCK}


def test_every_milestone_has_display_copy():
    for key in (e.MILESTONE_FIRST_BLOCK, e.MILESTONE_FIVE_MINUTES, e.MILESTONE_HALFWAY, e.MILESTONE_FIVE_K):
        assert {"title", "emoji", "share_text"} <= e.MILESTONES[key].keys()


# --- Progress ---------------------------------------------------------------------

def test_estimated_total_blocks():
    assert e.estimated_total_blocks(1, 1) == 12
    assert e.estimated_total_blocks(4, 3) == 13
    assert e.estimated_total_blocks(10, 12) == 10


def test_coming_up_hint():
    assert e.coming_up_hint(1) == "Soon you'll be jogging 2 minutes straight."
    assert e.coming_up_hint(5) == "Soon you'll be jogging 5 minutes straight."
    assert e.coming_up_hint(11) == "Soon you'll be heading out for your very first 5K."
    assert e.coming_up_hint(12) is None


# --- Age rules ------------------------------------------------------------------------

@pytest.mark.parametrize(
    "age,expected",
    [(None, 4), ("", 4), ("18_39", 4), ("40_54", 3), ("55_64", 2), ("65_plus", 2), ("under_18", 2)],
)
def test_start_level_capped_by_age(age, expected):
    assert e.start_level("active", "yes", age) == expected


def test_age_cap_never_raises_a_low_start():
    assert e.start_level("sitting", "not_yet", "65_plus") == 1
    assert e.start_level("walks", "yes", "40_54") == 3


@pytest.mark.parametrize("age", ["55_64", "65_plus", "under_18"])
def test_cautious_groups_never_jump_two_levels(age):
    assert e.next_level(3, e.TOO_EASY, previous_feedback=e.TOO_EASY, age_group=age).level == 4


@pytest.mark.parametrize("age", [None, "18_39", "40_54"])
def test_other_groups_can_jump_two(age):
    assert e.next_level(3, e.TOO_EASY, previous_feedback=e.TOO_EASY, age_group=age).level == 5


def test_65_plus_steps_down_on_first_too_hard():
    assert e.next_level(4, e.TOO_HARD, previous_feedback=e.JUST_RIGHT, age_group="65_plus").level == 3
    assert e.next_level(1, e.TOO_HARD, age_group="65_plus").level == 1
    assert e.next_level(4, e.TOO_HARD, previous_feedback=e.JUST_RIGHT, age_group="55_64").level == 4


def test_just_right_and_finish_unaffected_by_age():
    assert e.next_level(3, e.JUST_RIGHT, age_group="65_plus").level == 4
    assert e.next_level(12, e.JUST_RIGHT, age_group="65_plus").journey_complete


@pytest.mark.parametrize(
    "age,expected", [(None, 2), ("18_39", 2), ("40_54", 2), ("55_64", 3), ("65_plus", 3), ("under_18", 3)],
)
def test_min_gap_days_by_age(age, expected):
    assert e.min_gap_days(age, 2) == expected


def test_min_gap_setting_wins_if_larger():
    assert e.min_gap_days("65_plus", 4) == 4


def test_every_age_choice_has_rules():
    for value, _ in e.AGE_CHOICES:
        assert value in e.AGE_RULES
