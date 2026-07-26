from django.contrib import admin

from .models import ChatMessage, PrivateChat, PrivateMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("team", "author", "created_at", "edited_at", "is_deleted", "deleted_at", "attachment", "thumbnail")
    search_fields = ("team__name", "author__username", "author__email", "text")
    list_filter = ("team", "is_deleted", "created_at", "edited_at", "deleted_at")


@admin.register(PrivateChat)
class PrivateChatAdmin(admin.ModelAdmin):
    list_display = ("participant_1", "participant_2", "created_at", "updated_at")
    search_fields = (
        "participant_1__username",
        "participant_1__email",
        "participant_2__username",
        "participant_2__email",
    )
    list_filter = ("created_at", "updated_at")


@admin.register(PrivateMessage)
class PrivateMessageAdmin(admin.ModelAdmin):
    list_display = ("chat", "author", "created_at", "edited_at", "is_deleted", "deleted_at", "attachment", "thumbnail")
    search_fields = ("author__username", "author__email", "content")
    list_filter = ("is_deleted", "created_at", "edited_at", "deleted_at")
