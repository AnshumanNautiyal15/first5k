from django.urls import path

from . import views

app_name = "plans"

urlpatterns = [
    path("start/", views.start_activity, name="start"),
    path("start/2/", views.start_jog, name="start_jog"),
    path("your-first-block/", views.preview, name="preview"),
    path("today/", views.today, name="today"),
    path("day/<int:day_id>/complete/", views.complete_day, name="complete_day"),
]
