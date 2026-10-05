from django.urls import path

from . import views

app_name = "plans"

urlpatterns = [
    path("start/", views.start_activity, name="start"),
    path("start/2/", views.start_jog, name="start_jog"),
    path("start/3/", views.start_age, name="start_age"),
    path("your-first-block/", views.preview, name="preview"),
    path("today/", views.today, name="today"),
    path("progress/", views.progress, name="progress"),
    path("day/<int:day_id>/complete/", views.complete_day, name="complete_day"),
    path("block/<int:block_id>/feedback/", views.block_feedback, name="block_feedback"),
    path("block/next.ics", views.next_block_ics, name="next_block_ics"),
    path("milestone/<slug:key>/", views.milestone, name="milestone"),
    path("finished/", views.finished, name="finished"),
]
