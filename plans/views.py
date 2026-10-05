from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from . import engine, onboarding


@require_http_methods(["GET", "POST"])
def start_activity(request):
    if request.method == "POST" and onboarding.set_activity(request, request.POST.get("answer", "")):
        return redirect("plans:start_jog")
    return render(request, "plans/onboarding_question.html", {
        "step": 1,
        "question": "How active are you right now?",
        "hint": "There's no wrong answer. This just helps us pick a gentle start.",
        "choices": engine.ACTIVITY_CHOICES,
        "selected": onboarding.get_answers(request).get("activity"),
    })


@require_http_methods(["GET", "POST"])
def start_jog(request):
    answers = onboarding.get_answers(request)
    if "activity" not in answers:
        return redirect("plans:start")
    if request.method == "POST" and onboarding.set_jog_ability(request, request.POST.get("answer", "")):
        return redirect("plans:preview")
    return render(request, "plans/onboarding_question.html", {
        "step": 2,
        "question": "Could you jog for 1 minute without stopping?",
        "hint": "Be honest with yourself. Starting easy is the secret.",
        "choices": engine.JOG_CHOICES,
        "selected": answers.get("jog_ability"),
        "back_url": "plans:start",
    })


def preview(request):
    answers = onboarding.get_answers(request)
    if not onboarding.is_complete(answers):
        return redirect("plans:start")
    level = onboarding.starting_level(answers)
    return render(request, "plans/preview.html", {
        "level": engine.get_level(level),
        "steps": engine.session_steps(level),
        "total_minutes": engine.session_total_minutes(level),
        "rest_text": engine.REST_DAY_TEXT,
    })
