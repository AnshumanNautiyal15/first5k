from django.contrib import admin

from .models import OnboardingStart


@admin.register(OnboardingStart)
class OnboardingStartAdmin(admin.ModelAdmin):
    list_display = ("id", "activity", "jog_ability", "user", "created_at")
    list_filter = ("activity", "jog_ability", "created_at")
