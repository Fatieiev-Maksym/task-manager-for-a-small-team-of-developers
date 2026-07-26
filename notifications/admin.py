from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "actor", "task", "notification_type", "is_read", "created_at")
    search_fields = (
        "title",
        "message",
        "user__username",
        "user__email",
        "actor__username",
        "actor__email",
        "task__title",
    )
    list_filter = ("notification_type", "is_read", "created_at")
