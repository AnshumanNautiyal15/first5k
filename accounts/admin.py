from django.contrib import admin

from .models import MagicLoginToken, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "is_subscribed", "timezone", "created_at", "is_staff")
    list_filter = ("is_subscribed", "is_staff", "created_at")
    search_fields = ("email",)
    readonly_fields = ("created_at", "last_login")
    exclude = ("password",)


@admin.register(MagicLoginToken)
class MagicLoginTokenAdmin(admin.ModelAdmin):
    list_display = ("email", "ip", "created_at", "expires_at", "used_at")
    list_filter = ("created_at",)
    search_fields = ("email",)
    readonly_fields = [f.name for f in MagicLoginToken._meta.fields]
