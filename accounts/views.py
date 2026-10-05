from django import forms
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from notifications.email import send_magic_link
from plans import onboarding, services

from . import magic_link

GENERIC_SENT = "If that email is valid, a link is on its way. It works for 15 minutes."
RATE_LIMITED = ("You've asked for a few links already. Have a look in your inbox (and spam folder), "
                "or try again in a little while.")


class EmailForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            "class": "input", "autocomplete": "email", "inputmode": "email",
            "placeholder": "you@example.com", "required": True,
        }),
    )


def client_ip(request) -> str | None:
    # Behind a proxy, the last X-Forwarded-For hop is the one our proxy added.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[-1].strip() or None
    return request.META.get("REMOTE_ADDR")


def _send_link(request, form, is_signup: bool):
    """Shared handler for signup (from preview) and returning-user login."""
    email = magic_link.normalize_email(form.cleaned_data["email"])
    ip = client_ip(request)
    if magic_link.is_rate_limited(email, ip):
        form.add_error(None, RATE_LIMITED)
        return None
    answers = onboarding.get_answers(request) if is_signup else {}
    raw = magic_link.issue_token(email, ip, onboarding=answers)
    send_magic_link(email, raw, is_signup=is_signup)
    request.session["check_email"] = {"email": email if is_signup else "", "is_signup": is_signup}
    return redirect("accounts:check_email")


@require_POST
def signup(request):
    """Email form on the preview page."""
    if not onboarding.is_complete(onboarding.get_answers(request)):
        return redirect("plans:start")
    form = EmailForm(request.POST)
    if form.is_valid() and (resp := _send_link(request, form, is_signup=True)):
        return resp
    return render(request, "plans/preview.html", {**_preview_context(request), "form": form}, status=400)


def _preview_context(request):
    from plans.views import preview_context
    return preview_context(onboarding.get_answers(request))


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("plans:today")
    form = EmailForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and (resp := _send_link(request, form, is_signup=False)):
        return resp
    return render(request, "accounts/login.html", {"form": form})


def check_email(request):
    info = request.session.get("check_email")
    if not info:
        return redirect("core:landing")
    return render(request, "accounts/check_email.html", {
        "email": info.get("email"), "is_signup": info.get("is_signup"), "generic": GENERIC_SENT,
    })


@require_http_methods(["GET", "POST"])
def verify(request, token):
    """
    GET shows a one-tap confirm button; POST redeems. Email security scanners often
    prefetch links with GET, which would otherwise burn single-use tokens.
    """
    if request.method == "GET":
        valid = magic_link.find_valid(token) is not None
        return render(request, "accounts/verify.html", {"valid": valid, "form": EmailForm()}, status=200 if valid else 410)

    redeemed = magic_link.redeem(token)
    if redeemed is None:
        return render(request, "accounts/verify.html", {"valid": False, "form": EmailForm()}, status=410)

    # Prefer answers from this browser's session, else those carried by the link.
    answers = onboarding.get_answers(request)
    if not onboarding.is_complete(answers):
        answers = redeemed.onboarding
    login(request, redeemed.user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.pop("check_email", None)

    user = redeemed.user
    if not hasattr(user, "journey"):
        if not onboarding.is_complete(answers):
            return redirect("plans:start")
        services.create_journey(user, answers["activity"], answers["jog_ability"], answers.get("start_id"))
        request.session.pop(onboarding.SESSION_KEY, None)
    return redirect("plans:today")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("core:landing")
