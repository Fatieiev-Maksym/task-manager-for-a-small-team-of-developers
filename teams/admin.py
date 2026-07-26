from django.contrib import admin

from .models import Team, TeamMember


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "meeting_url", "created_at")
    search_fields = ("name", "description", "meeting_url", "owner__username", "owner__email")
    list_filter = ("created_at",)


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("team", "user", "role", "joined_at")
    search_fields = ("team__name", "user__username", "user__email")
    list_filter = ("role", "joined_at")
