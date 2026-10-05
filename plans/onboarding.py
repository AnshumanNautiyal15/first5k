"""Onboarding answers live in the anonymous session until the user verifies their email."""

from . import engine
from .models import OnboardingStart

SESSION_KEY = "onboarding"

_VALID_ACTIVITY = {value for value, _ in engine.ACTIVITY_CHOICES}
_VALID_JOG = {value for value, _ in engine.JOG_CHOICES}
_VALID_AGE = {value for value, _ in engine.AGE_CHOICES}


def get_answers(request) -> dict:
    return request.session.get(SESSION_KEY, {})


def set_activity(request, activity: str) -> bool:
    if activity not in _VALID_ACTIVITY:
        return False
    if not request.session.session_key:
        request.session.save()
    answers = get_answers(request)
    start_id = answers.get("start_id")
    if start_id:
        OnboardingStart.objects.filter(pk=start_id).update(activity=activity)
    else:
        start = OnboardingStart.objects.create(session_key=request.session.session_key, activity=activity)
        start_id = start.pk
    request.session[SESSION_KEY] = {"activity": activity, "start_id": start_id}
    return True


def set_jog_ability(request, jog_ability: str) -> bool:
    answers = get_answers(request)
    if jog_ability not in _VALID_JOG or "activity" not in answers:
        return False
    answers["jog_ability"] = jog_ability
    request.session[SESSION_KEY] = answers
    OnboardingStart.objects.filter(pk=answers.get("start_id")).update(jog_ability=jog_ability)
    return True


def set_age_group(request, age_group: str) -> bool:
    answers = get_answers(request)
    if age_group not in _VALID_AGE or "jog_ability" not in answers:
        return False
    answers["age_group"] = age_group
    request.session[SESSION_KEY] = answers
    OnboardingStart.objects.filter(pk=answers.get("start_id")).update(age_group=age_group)
    return True


def is_complete(answers: dict) -> bool:
    return all(k in answers for k in ("activity", "jog_ability", "age_group"))


def starting_level(answers: dict) -> int:
    return engine.start_level(answers.get("activity", ""), answers.get("jog_ability", ""), answers.get("age_group"))
