"""Admin registrations for support tasks."""

from django.contrib import admin

from accounts.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "nickname", "client_id", "created_at")
    search_fields = ("user__username", "nickname", "client_id")
    readonly_fields = ("client_id", "created_at", "updated_at")
