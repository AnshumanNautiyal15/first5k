from django.shortcuts import redirect, render


def landing(request):
    if request.user.is_authenticated:
        return redirect("plans:today")
    return render(request, "core/landing.html")
