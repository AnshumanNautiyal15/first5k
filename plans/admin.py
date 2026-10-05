from django.contrib import admin

from . import services
from .models import Block, DayLog, Journey, Milestone, OnboardingStart


@admin.register(OnboardingStart)
class OnboardingStartAdmin(admin.ModelAdmin):
    list_display = ("id", "activity", "jog_ability", "user", "created_at")
    list_filter = ("activity", "jog_ability", "created_at")


class BlockInline(admin.TabularInline):
    model = Block
    extra = 0
    fields = ("index", "level", "status", "unlocks_at", "started_at", "completed_at", "feedback", "entry_note")
    show_change_link = True


@admin.register(Journey)
class JourneyAdmin(admin.ModelAdmin):
    list_display = ("user", "current_level", "blocks_completed", "last_activity_at", "completed_at", "created_at")
    list_filter = ("current_level", "start_activity", "start_jog_ability", ("completed_at", admin.EmptyFieldListFilter))
    search_fields = ("user__email",)
    inlines = [BlockInline]


class DayLogInline(admin.TabularInline):
    model = DayLog
    extra = 0
    fields = ("day_number", "kind", "completed_at", "compliment")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("journey", "index", "level", "status", "feedback", "unlocks_at", "completed_at")
    list_filter = ("status", "feedback", "level", "entry_note")
    search_fields = ("journey__user__email",)
    inlines = [DayLogInline]
    actions = ["unlock_now"]

    @admin.action(description="Unlock now (skip the wait, for testing)")
    def unlock_now(self, request, queryset):
        locked = queryset.filter(status=Block.Status.LOCKED)
        for block in locked:
            services.unlock_now(block)
        self.message_user(request, f"{locked.count()} block(s) will unlock on the user's next visit.")


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ("journey", "key", "achieved_at", "seen_at")
    list_filter = ("key", "achieved_at")
    search_fields = ("journey__user__email",)
