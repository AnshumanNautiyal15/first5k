from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("auth/signup/", views.signup, name="signup"),
    path("auth/login/", views.login_view, name="login"),
    path("auth/verify/<str:token>/", views.verify, name="verify"),
    path("auth/logout/", views.logout_view, name="logout"),
    path("check-email/", views.check_email, name="check_email"),
]
