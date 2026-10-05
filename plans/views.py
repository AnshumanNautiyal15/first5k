from django.conf import settings
from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from . import charts, engine, fuel, ics, learn, onboarding, services
from .models import Block, DayLog, Journey, Milestone


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
        return redirect("plans:start_age")
    return render(request, "plans/onboarding_question.html", {
        "step": 2,
        "question": "Could you jog for 1 minute without stopping?",
        "hint": "Be honest with yourself. Starting easy is the secret.",
        "choices": engine.JOG_CHOICES,
        "selected": answers.get("jog_ability"),
        "back_url": "plans:start",
    })


@require_http_methods(["GET", "POST"])
def start_age(request):
    answers = onboarding.get_answers(request)
    if "jog_ability" not in answers:
        return redirect("plans:start_jog" if "activity" in answers else "plans:start")
    if request.method == "POST" and onboarding.set_age_group(request, request.POST.get("answer", "")):
        # Logged-in users without a journey go straight to their plan.
        return redirect("plans:today" if request.user.is_authenticated else "plans:preview")
    return render(request, "plans/onboarding_question.html", {
        "step": 3,
        "question": "How old are you?",
        "hint": "Bodies need different amounts of recovery at different ages. We'll pace your plan to suit you.",
        "choices": engine.AGE_CHOICES,
        "selected": answers.get("age_group"),
        "back_url": "plans:start_jog",
    })


def preview_context(answers: dict) -> dict:
    level = onboarding.starting_level(answers)
    return {
        "is_minor": answers.get("age_group") == "under_18",
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
    journey = services.create_journey(request.user, answers["activity"], answers["jog_ability"], answers.get("start_id"),
                                      age_group=answers.get("age_group", ""))
    request.session.pop(onboarding.SESSION_KEY, None)
    return journey


def _day_cards(block: Block) -> list[dict]:
    cards = []
    for day in block.days.all():
        card = {"day": day, "lesson": learn.lesson_for(day.kind, block.level)}
        if day.kind == "run":
            card.update(
                level=block.level_info,
                steps=engine.session_steps(block.level),
                total_minutes=engine.session_total_minutes(block.level),
                fuel=fuel.fuel_tip(block.index),
            )
        cards.append(card)
    return cards


def _milestone_url(journey: Journey) -> str | None:
    unseen = services.next_unseen_milestone(journey)
    return reverse("plans:milestone", args=[unseen.key]) if unseen else None


@login_required
def today(request):
    journey = _get_or_create_journey(request)
    if journey is None:
        return redirect("plans:start")
    skip_wait = settings.DEBUG and request.GET.get("skip_wait") == "1"
    result = services.refresh(journey, skip_wait=skip_wait)
    if result.message:
        flash.info(request, result.message)
    block = result.block
    if block is None:
        return redirect("plans:finished" if journey.is_complete else "core:landing")

    context = {
        "journey": journey,
        "current": block,
        "total_blocks": engine.estimated_total_blocks(block.index, block.level),
        "hint": engine.coming_up_hint(block.level),
        "milestone_url": _milestone_url(journey),
    }
    if block.status == Block.Status.LOCKED:
        context["unlocks_at"] = block.unlocks_at
        return render(request, "plans/waiting.html", context)
    return render(request, "plans/today.html", {
        **context,
        "cards": _day_cards(block),
        "rest_text": engine.REST_DAY_TEXT,
        "feedback_choices": [c for c in engine.FEEDBACK_CHOICES if c[0] != engine.DIDNT_DO],
    })


@login_required
@require_POST
def complete_day(request, day_id):
    day = get_object_or_404(
        DayLog.objects.select_related("block__journey"),
        pk=day_id, block__journey__user=request.user, block__status=Block.Status.ACTIVE,
    )
    result = services.complete_day(day)
    milestone_url = _milestone_url(day.block.journey)
    if wants_json(request):
        return JsonResponse({
            "ok": True,
            "message": result.message,
            "already_done": result.already_done,
            "block_done": result.block_done,
            "milestone_url": milestone_url,
        })
    if not result.already_done:
        flash.success(request, result.message)
    return redirect("plans:today")


# --- Feedback ---------------------------------------------------------------------------

@login_required
@require_http_methods(["GET", "POST"])
def block_feedback(request, block_id):
    block = get_object_or_404(Block, pk=block_id, journey__user=request.user)
    if block.status != Block.Status.ACTIVE:
        return redirect("plans:today")
    if request.method == "GET":
        return render(request, "plans/feedback.html", {
            "current": block,
            "feedback_choices": [c for c in engine.FEEDBACK_CHOICES if c[0] != engine.DIDNT_DO],
        })

    feedback = request.POST.get("feedback", "")
    if feedback not in {v for v, _ in engine.FEEDBACK_CHOICES}:
        return redirect("plans:block_feedback", block_id=block.pk)
    result = services.submit_feedback(block, feedback)
    journey = block.journey
    journey.refresh_from_db()
    if result.journey_complete:
        target = reverse("plans:finished")
    else:
        target = _milestone_url(journey) or reverse("plans:today")
    if wants_json(request):
        return JsonResponse({"ok": True, "message": result.message, "redirect": target})
    if result.message:
        flash.success(request, result.message)
    return redirect(target)


# --- Milestones, finish, calendar, progress -----------------------------------------------

@login_required
def milestone(request, key):
    if key not in engine.MILESTONES:
        raise Http404
    m = get_object_or_404(Milestone, journey__user=request.user, key=key)
    if m.seen_at is None:
        Milestone.objects.filter(pk=m.pk).update(seen_at=timezone.now())
    from . import messages as msgs
    journey = m.journey
    return render(request, "plans/milestone.html", {
        "milestone": m,
        "info": m.info,
        "message": msgs.pick(f"milestone_{key}").text,
        "next_url": _milestone_url(journey) or reverse("plans:finished" if journey.is_complete else "plans:today"),
    })


@login_required
def finished(request):
    journey = get_object_or_404(Journey, user=request.user)
    if not journey.is_complete:
        return redirect("plans:today")
    unseen = services.next_unseen_milestone(journey)
    if unseen:
        return redirect("plans:milestone", key=unseen.key)
    return render(request, "plans/finished.html", {"journey": journey, "stats": services.progress_stats(journey)})


@login_required
def next_block_ics(request):
    journey = get_object_or_404(Journey, user=request.user)
    block = services.current_block(journey)
    if block is None or block.status != Block.Status.LOCKED:
        raise Http404
    level = block.level_info
    body = ics.event(
        uid=f"block-{block.pk}@first5k",
        start=block.unlocks_at,
        summary="First5K: your next 2 days are ready 👟",
        description=(f"Next up: {level['title']}. {engine.session_summary(block.level)}. "
                     f"Open your plan: {settings.SITE_URL}{reverse('plans:today')}"),
        url=f"{settings.SITE_URL}{reverse('plans:today')}",
    )
    resp = HttpResponse(body, content_type="text/calendar; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="first5k-next-block.ics"'
    return resp


@login_required
def progress(request):
    journey = Journey.objects.filter(user=request.user).first()
    if journey is None:
        return redirect("plans:start")
    stats = services.progress_stats(journey)
    points = []
    for r in stats["runs"]:
        day = timezone.localtime(r["date"])
        minutes = r["jog_minutes"]
        points.append({
            "label": str(r["number"]),
            "value": minutes,
            "tooltip": f"Run {r['number']} · {day:%-d %b}: {minutes} min jogging",
        })
    block = services.current_block(journey)
    return render(request, "plans/progress.html", {
        "journey": journey, "stats": stats, "chart": charts.bar_chart(points),
        "level_is_next": block is not None and block.status == Block.Status.LOCKED,
    })
