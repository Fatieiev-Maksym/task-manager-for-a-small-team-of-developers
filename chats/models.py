import os
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db import models
from PIL import Image, ImageOps

from teams.models import Team


User = get_user_model()

MAX_CHAT_ATTACHMENT_SIZE = 10 * 1024 * 1024
ALLOWED_CHAT_ATTACHMENT_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "txt",
    "png",
    "jpg",
    "jpeg",
    "webp",
}
IMAGE_CHAT_ATTACHMENT_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp",
}
BLOCKED_CHAT_ATTACHMENT_EXTENSIONS = {
    "exe",
    "bat",
    "cmd",
    "ps1",
    "js",
    "html",
    "php",
    "sh",
}


def validate_chat_attachment(file):
    if file.size > MAX_CHAT_ATTACHMENT_SIZE:
        raise ValidationError("Розмір файлу не може перевищувати 10 МБ.")

    extension = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
    if extension in BLOCKED_CHAT_ATTACHMENT_EXTENSIONS or extension not in ALLOWED_CHAT_ATTACHMENT_EXTENSIONS:
        raise ValidationError("Цей тип файлу не дозволено для вкладень чату.")


def get_attachment_extension(file):
    if not file:
        return ""

    filename = file.name or ""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def get_attachment_filename(file):
    if not file:
        return ""

    return file.name.rsplit("/", 1)[-1]


def build_thumbnail_content(file):
    file.open("rb")
    with Image.open(file) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((900, 500))

        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        thumb_io = BytesIO()
        image.save(thumb_io, format="JPEG", quality=85, optimize=True)
        return ContentFile(thumb_io.getvalue())


def build_thumbnail_name(file):
    base_name = os.path.splitext(os.path.basename(file.name))[0]
    return f"{base_name}_thumb.jpg"


class ChatMessage(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="chat_messages")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_messages")
    text = models.TextField()
    attachment = models.FileField(
        upload_to="chat_attachments/%Y/%m/%d/",
        blank=True,
        null=True,
        validators=[validate_chat_attachment],
    )
    thumbnail = models.ImageField(
        upload_to="chat_attachments/thumbnails/",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_chat_messages",
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author} in {self.team}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.attachment and self.is_image_attachment and not self.thumbnail:
            self.create_thumbnail()

    def create_thumbnail(self):
        if not self.attachment or not self.is_image_attachment:
            return False

        try:
            thumbnail_content = build_thumbnail_content(self.attachment)
            self.thumbnail.save(
                build_thumbnail_name(self.attachment),
                thumbnail_content,
                save=False,
            )
            super().save(update_fields=["thumbnail"])
            return True
        except Exception:
            return False

    @property
    def attachment_extension(self):
        return get_attachment_extension(self.attachment)

    @property
    def attachment_filename(self):
        return get_attachment_filename(self.attachment)

    @property
    def is_image_attachment(self):
        return self.attachment_extension in IMAGE_CHAT_ATTACHMENT_EXTENSIONS


class PrivateChat(models.Model):
    participant_1 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="private_chats_as_participant_1",
    )
    participant_2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="private_chats_as_participant_2",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["participant_1", "participant_2"],
                name="unique_private_chat_pair",
            )
        ]

    def clean(self):
        if self.participant_1_id and self.participant_1_id == self.participant_2_id:
            raise ValidationError("Приватний чат має бути між двома різними користувачами.")

    def save(self, *args, **kwargs):
        if self.participant_1_id and self.participant_2_id:
            if self.participant_1_id == self.participant_2_id:
                raise ValidationError("Приватний чат має бути між двома різними користувачами.")
            if self.participant_1_id > self.participant_2_id:
                self.participant_1_id, self.participant_2_id = self.participant_2_id, self.participant_1_id

        super().save(*args, **kwargs)

    def get_other_participant(self, user):
        if self.participant_1_id == user.id:
            return self.participant_2
        return self.participant_1

    def __str__(self):
        return f"{self.participant_1} - {self.participant_2}"


class PrivateMessage(models.Model):
    chat = models.ForeignKey(PrivateChat, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="private_messages")
    content = models.TextField()
    attachment = models.FileField(
        upload_to="private_chat_attachments/%Y/%m/%d/",
        blank=True,
        null=True,
        validators=[validate_chat_attachment],
    )
    thumbnail = models.ImageField(
        upload_to="private_chat_attachments/thumbnails/",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Private message by {self.author}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.attachment and self.is_image_attachment and not self.thumbnail:
            self.create_thumbnail()

    def create_thumbnail(self):
        if not self.attachment or not self.is_image_attachment:
            return False

        try:
            thumbnail_content = build_thumbnail_content(self.attachment)
            self.thumbnail.save(
                build_thumbnail_name(self.attachment),
                thumbnail_content,
                save=False,
            )
            super().save(update_fields=["thumbnail"])
            return True
        except Exception:
            return False

    @property
    def attachment_extension(self):
        return get_attachment_extension(self.attachment)

    @property
    def attachment_filename(self):
        return get_attachment_filename(self.attachment)

    @property
    def is_image_attachment(self):
        return self.attachment_extension in IMAGE_CHAT_ATTACHMENT_EXTENSIONS
