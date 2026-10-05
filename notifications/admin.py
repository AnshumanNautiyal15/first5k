from django.contrib import admin

from .models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "ref", "sent_at")
    list_filter = ("kind", "sent_at")
    search_fields = ("user__email", "ref")
    readonly_fields = ("user", "kind", "ref", "block", "sent_at")
