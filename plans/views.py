from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from . import engine, onboarding, services
from .models import Block, DayLog, Journey


def wants_json(request) -> bool:
    return "application/json" in request.headers.get("Accept", "")


# --- Onboarding -------------------------------------------------------------------

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
        # Logged-in users without a journey go straight to their plan.
        return redirect("plans:today" if request.user.is_authenticated else "plans:preview")
    return render(request, "plans/onboarding_question.html", {
        "step": 2,
        "question": "Could you jog for 1 minute without stopping?",
        "hint": "Be honest with yourself. Starting easy is the secret.",
        "choices": engine.JOG_CHOICES,
        "selected": answers.get("jog_ability"),
        "back_url": "plans:start",
    })


def preview_context(answers: dict) -> dict:
    level = onboarding.starting_level(answers)
    return {
        "level": engine.get_level(level),
        "steps": engine.session_steps(level),
        "total_minutes": engine.session_total_minutes(level),
        "rest_text": engine.REST_DAY_TEXT,
    }


def preview(request):
    if request.user.is_authenticated:
        return redirect("plans:today")
    answers = onboarding.get_answers(request)
    if not onboarding.is_complete(answers):
        return redirect("plans:start")
    from accounts.views import EmailForm
    return render(request, "plans/preview.html", {**preview_context(answers), "form": EmailForm()})


# --- Dashboard ---------------------------------------------------------------------

def _get_or_create_journey(request) -> Journey | None:
    journey = Journey.objects.filter(user=request.user).first()
    if journey:
        return journey
    answers = onboarding.get_answers(request)
    if not onboarding.is_complete(answers):
        return None
    journey = services.create_journey(request.user, answers["activity"], answers["jog_ability"], answers.get("start_id"))
    request.session.pop(onboarding.SESSION_KEY, None)
    return journey


def _day_cards(block: Block) -> list[dict]:
    cards = []
    for day in block.days.all():
        card = {"day": day}
        if day.kind == "run":
            card.update(
                level=block.level_info,
                steps=engine.session_steps(block.level),
                total_minutes=engine.session_total_minutes(block.level),
            )
        cards.append(card)
    return cards


@login_required
def today(request):
    journey = _get_or_create_journey(request)
    if journey is None:
        return redirect("plans:start")
    block = services.current_block(journey)
    if block is None:
        return redirect("core:landing")
    return render(request, "plans/today.html", {
        "journey": journey,
        "current": block,
        "cards": _day_cards(block),
        "rest_text": engine.REST_DAY_TEXT,
        "total_blocks": engine.estimated_total_blocks(block.index, block.level),
        "hint": engine.coming_up_hint(block.level),
    })


@login_required
@require_POST
def complete_day(request, day_id):
    day = get_object_or_404(
        DayLog.objects.select_related("block__journey"),
        pk=day_id, block__journey__user=request.user, block__status=Block.Status.ACTIVE,
    )
    result = services.complete_day(day)
    if wants_json(request):
        return JsonResponse({
            "ok": True,
            "message": result.message,
            "already_done": result.already_done,
            "block_done": result.block_done,
        })
    if not result.already_done:
        flash.success(request, result.message)
    return redirect("plans:today")
