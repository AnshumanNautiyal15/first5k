from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("unsubscribe/<str:token>/", views.unsubscribe, name="unsubscribe"),
]
