from django.contrib import admin

from .models import Comment, Task, TaskAttachment, TaskCommentAttachment, TaskStatus, TaskSubmission


@admin.register(TaskStatus)
class TaskStatusAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "order")
    search_fields = ("name", "project__name")
    list_filter = ("project",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "priority", "assignee", "deadline", "created_at")
    search_fields = (
        "title",
        "description",
        "project__name",
        "assignee__username",
        "assignee__email",
        "created_by__username",
    )
    list_filter = ("project", "status", "priority", "deadline", "created_at")


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ("task", "uploaded_by", "uploaded_at", "file")
    search_fields = ("task__title", "uploaded_by__username", "uploaded_by__email", "original_name", "file")
    list_filter = ("uploaded_at",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("task", "author", "created_at")
    search_fields = ("task__title", "author__username", "author__email", "text")
    list_filter = ("created_at",)


@admin.register(TaskCommentAttachment)
class TaskCommentAttachmentAdmin(admin.ModelAdmin):
    list_display = ("comment", "file", "thumbnail", "uploaded_at")
    search_fields = ("comment__task__title", "comment__author__username", "file")
    list_filter = ("uploaded_at",)


@admin.register(TaskSubmission)
class TaskSubmissionAdmin(admin.ModelAdmin):
    list_display = ("task", "submitted_by", "created_at", "result_link", "attachment")
    search_fields = ("task__title", "submitted_by__username", "submitted_by__email", "description", "result_link")
    list_filter = ("created_at",)
