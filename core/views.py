from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET


def landing(request):
    if request.user.is_authenticated:
        return redirect("plans:today")
    return render(request, "core/landing.html")


def privacy(request):
    return render(request, "core/privacy.html")


def terms(request):
    return render(request, "core/terms.html")


def health(request):
    return render(request, "core/health.html")


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /$",
        "Allow: /start/",
        "Allow: /privacy/",
        "Allow: /terms/",
        "Allow: /health/",
        "Disallow: /",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
