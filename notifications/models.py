from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        TASK_ASSIGNED = "task_assigned", "Task assigned"
        TASK_STARTED = "task_started", "Task started"
        TASK_SUBMITTED = "task_submitted", "Task submitted"
        TASK_APPROVED = "task_approved", "Task approved"
        TASK_REJECTED = "task_rejected", "Task rejected"
        TASK_UPDATED = "task_updated", "Task updated"
        TASK_COMMENTED = "task_commented", "Task commented"
        DEADLINE_SOON = "deadline_soon", "Deadline soon"
        TASK_OVERDUE = "task_overdue", "Task overdue"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_notifications",
    )
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=50,
        choices=Type.choices,
        default=Type.TASK_UPDATED,
    )
    title = models.CharField(max_length=150)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
