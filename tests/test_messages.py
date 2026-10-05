import random

import pytest

from plans import messages as m


def test_at_least_30_messages():
    assert sum(len(v) for v in m.MESSAGES.values()) >= 30


@pytest.mark.parametrize("group", [
    "first_ever", "standard", "after_gap", "harder_level", "rest",
    "milestone_first_block", "milestone_five_minutes", "milestone_halfway", "milestone_five_k",
    "welcome_back", "ease_down",
    "feedback_too_easy", "feedback_just_right", "feedback_too_hard", "feedback_didnt_do",
])
def test_required_groups_exist_with_variety(group):
    assert len(m.MESSAGES[group]) >= 2


def test_all_messages_distinct():
    all_msgs = [t for group in m.MESSAGES.values() for t in group]
    assert len(all_msgs) == len(set(all_msgs))


def test_tone_has_no_guilt_words():
    banned = ["streak", "failed", "lazy", "should have", "missed", "excuse", "disappoint"]
    for text in (t for group in m.MESSAGES.values() for t in group):
        for word in banned:
            assert word not in text.lower(), text


def test_templating():
    msg = m.pick("harder_level", minutes=8)
    assert "8 minutes" in msg.text
    assert "{" not in msg.text


def test_never_repeats_twice_in_a_row():
    rng = random.Random(1)
    last = ""
    for _ in range(200):
        msg = m.pick("standard", last_key=last, rng=rng)
        assert msg.key != last
        last = msg.key


def test_completion_group_priority():
    g = m.completion_group
    assert g(kind="run", is_first_ever=True, after_gap=True, is_longest_jog=True) == "first_ever"
    assert g(kind="rest", is_first_ever=False, after_gap=True, is_longest_jog=False) == "rest"
    assert g(kind="run", is_first_ever=False, after_gap=True, is_longest_jog=True) == "after_gap"
    assert g(kind="run", is_first_ever=False, after_gap=False, is_longest_jog=True) == "harder_level"
    assert g(kind="run", is_first_ever=False, after_gap=False, is_longest_jog=False) == "standard"
