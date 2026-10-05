from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .unsubscribe import user_for_token


@csrf_exempt  # The signed token is the credential; RFC 8058 one-click POSTs carry no CSRF token.
@require_http_methods(["GET", "POST"])
def unsubscribe(request, token):
    user = user_for_token(token)
    if user is None:
        return render(request, "notifications/unsubscribe.html", {"invalid": True}, status=404)
    if request.method == "POST":
        if user.is_subscribed:
            user.is_subscribed = False
            user.save(update_fields=["is_subscribed"])
        return render(request, "notifications/unsubscribe.html", {"done": True})
    return render(request, "notifications/unsubscribe.html", {"email": user.email})
