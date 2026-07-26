from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from chats.models import (
    IMAGE_CHAT_ATTACHMENT_EXTENSIONS,
    build_thumbnail_content,
    build_thumbnail_name,
    get_attachment_extension,
    get_attachment_filename,
    validate_chat_attachment,
)
from projects.models import Project


User = get_user_model()

MAX_TASK_ATTACHMENT_SIZE = 10 * 1024 * 1024
ALLOWED_TASK_ATTACHMENT_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "txt",
    "zip",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
}
IMAGE_TASK_ATTACHMENT_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
}


def validate_task_attachment(file):
    if file.size > MAX_TASK_ATTACHMENT_SIZE:
        raise ValidationError("Файл не може перевищувати 10 МБ.")

    extension = get_attachment_extension(file)
    if extension not in ALLOWED_TASK_ATTACHMENT_EXTENSIONS:
        raise ValidationError("Цей тип файлу не дозволено для вкладень задачі.")


class TaskStatus(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="statuses")
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["project__name", "order", "name"]

    def __str__(self):
        return f"{self.project}: {self.name}"


class Task(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.ForeignKey(TaskStatus, on_delete=models.PROTECT, related_name="tasks")
    assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_tasks")
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(
        upload_to="task_attachments/%Y/%m/%d/",
        validators=[validate_task_attachment],
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="task_attachments")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    original_name = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"Attachment for task {self.task_id}"

    def save(self, *args, **kwargs):
        if self.file and not self.original_name:
            self.original_name = get_attachment_filename(self.file)[:255]
        super().save(*args, **kwargs)

    @property
    def file_extension(self):
        return get_attachment_extension(self.file)

    @property
    def file_name(self):
        return self.original_name or get_attachment_filename(self.file)

    @property
    def is_image_attachment(self):
        return self.file_extension in IMAGE_TASK_ATTACHMENT_EXTENSIONS


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="task_comments")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.task}"


class TaskCommentAttachment(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(
        upload_to="task_comment_attachments/%Y/%m/%d/",
        validators=[validate_chat_attachment],
    )
    thumbnail = models.ImageField(
        upload_to="task_comment_attachments/thumbnails/",
        blank=True,
        null=True,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"Attachment for comment {self.comment_id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.file and self.is_image_attachment and not self.thumbnail:
            self.create_thumbnail()

    def create_thumbnail(self):
        if not self.file or not self.is_image_attachment:
            return False

        try:
            thumbnail_content = build_thumbnail_content(self.file)
            self.thumbnail.save(
                build_thumbnail_name(self.file),
                thumbnail_content,
                save=False,
            )
            super().save(update_fields=["thumbnail"])
            return True
        except Exception:
            return False

    @property
    def file_extension(self):
        return get_attachment_extension(self.file)

    @property
    def file_name(self):
        return get_attachment_filename(self.file)

    @property
    def is_image_attachment(self):
        return self.file_extension in IMAGE_CHAT_ATTACHMENT_EXTENSIONS


class TaskSubmission(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="submissions")
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="task_submissions")
    description = models.TextField()
    result_link = models.URLField(blank=True)
    attachment = models.FileField(upload_to="task_submissions/%Y/%m/%d/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Submission for {self.task} by {self.submitted_by}"
