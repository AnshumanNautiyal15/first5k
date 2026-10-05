"""Adds a read-only funnel stats page to the Django admin at /admin/stats/."""

from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path

from . import stats


def stats_view(request):
    period = request.GET.get("period", "30")
    if period not in stats.PERIODS:
        period = "30"
    context = {
        **admin.site.each_context(request),
        "title": "Funnel stats",
        "period": period,
        "periods": [("7", "7 days"), ("30", "30 days"), ("90", "90 days"), ("all", "All time")],
        "data": stats.funnel(stats.PERIODS[period]),
    }
    return TemplateResponse(request, "admin/stats.html", context)


_original_get_urls = admin.site.get_urls


def _get_urls():
    return [path("stats/", admin.site.admin_view(stats_view), name="stats")] + _original_get_urls()


admin.site.get_urls = _get_urls
admin.site.site_header = "First5K admin"
admin.site.site_title = "First5K admin"
