from django.core.management.base import BaseCommand

from chats.models import ChatMessage, PrivateMessage


class Command(BaseCommand):
    help = "Generate thumbnails for old chat image attachments."

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        errors = 0

        for model in (ChatMessage, PrivateMessage):
            queryset = model.objects.exclude(attachment="").exclude(attachment__isnull=True)
            for message in queryset.iterator():
                if not message.is_image_attachment or message.thumbnail:
                    skipped += 1
                    continue

                if message.create_thumbnail():
                    created += 1
                else:
                    errors += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Thumbnails created: {created}; skipped: {skipped}; errors: {errors}."
            )
        )
