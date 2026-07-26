from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.models import Notification
from notifications.utils import create_notification
from tasks.models import Task


STATUS_DONE = "Done"


class Command(BaseCommand):
    help = "Checks task deadlines and creates deadline notifications."

    def handle(self, *args, **options):
        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)

        deadline_soon_created = 0
        overdue_created = 0
        skipped_existing = 0

        tasks = (
            Task.objects.filter(deadline__isnull=False)
            .exclude(status__name__iexact=STATUS_DONE)
            .select_related("assignee", "project__team__owner", "status")
        )

        for task in tasks:
            if today <= task.deadline <= tomorrow:
                created, skipped = self.create_deadline_notifications(
                    task=task,
                    notification_type=Notification.Type.DEADLINE_SOON,
                    assignee_title="Наближається дедлайн",
                    owner_title="Наближається дедлайн задачі",
                    assignee_message=self.get_deadline_soon_assignee_message(task),
                    owner_message=self.get_deadline_soon_owner_message(task),
                )
                deadline_soon_created += created
                skipped_existing += skipped
            elif task.deadline < today:
                created, skipped = self.create_deadline_notifications(
                    task=task,
                    notification_type=Notification.Type.TASK_OVERDUE,
                    assignee_title="Задачу прострочено",
                    owner_title="Прострочена задача",
                    assignee_message=self.get_overdue_assignee_message(task),
                    owner_message=self.get_overdue_owner_message(task),
                )
                overdue_created += created
                skipped_existing += skipped

        self.stdout.write(self.style.SUCCESS("Deadline check completed."))
        self.stdout.write(f"Deadline soon notifications created: {deadline_soon_created}")
        self.stdout.write(f"Overdue notifications created: {overdue_created}")
        self.stdout.write(f"Skipped existing notifications: {skipped_existing}")

    def create_deadline_notifications(
        self,
        task,
        notification_type,
        assignee_title,
        owner_title,
        assignee_message,
        owner_message,
    ):
        created_count = 0
        skipped_count = 0
        recipients = []

        if task.assignee:
            recipients.append((task.assignee, assignee_title, assignee_message))

        owner = task.project.team.owner
        if owner and owner.id != task.assignee_id:
            recipients.append((owner, owner_title, owner_message))

        for recipient, title, message in recipients:
            if self.notification_exists(recipient, task, notification_type):
                skipped_count += 1
                continue

            notification = create_notification(
                recipient=recipient,
                actor=None,
                task=task,
                notification_type=notification_type,
                title=title,
                message=message,
            )
            if notification:
                created_count += 1

        return created_count, skipped_count

    def notification_exists(self, recipient, task, notification_type):
        return Notification.objects.filter(
            user=recipient,
            task=task,
            notification_type=notification_type,
        ).exists()

    def get_deadline_soon_assignee_message(self, task):
        return f'Наближається дедлайн задачі "{task.title}". Дедлайн: {self.format_date(task.deadline)}.'

    def get_deadline_soon_owner_message(self, task):
        if task.assignee:
            return (
                f'Наближається дедлайн задачі "{task.title}", призначеної користувачу '
                f"{task.assignee.username}. Дедлайн: {self.format_date(task.deadline)}."
            )
        return (
            f'Наближається дедлайн задачі "{task.title}". Виконавця не призначено. '
            f"Дедлайн: {self.format_date(task.deadline)}."
        )

    def get_overdue_assignee_message(self, task):
        return f'Задача "{task.title}" прострочена. Дедлайн був: {self.format_date(task.deadline)}.'

    def get_overdue_owner_message(self, task):
        if task.assignee:
            return (
                f'Задача "{task.title}", призначена користувачу {task.assignee.username}, '
                f"прострочена. Дедлайн був: {self.format_date(task.deadline)}."
            )
        return (
            f'Задача "{task.title}" прострочена. Виконавця не призначено. '
            f"Дедлайн був: {self.format_date(task.deadline)}."
        )

    def format_date(self, value):
        return value.strftime("%d.%m.%Y")
