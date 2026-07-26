from .models import Notification


def create_notification(recipient, actor, task, notification_type, title, message):
    if not recipient:
        return None
    if actor and recipient.pk == actor.pk:
        return None

    try:
        return Notification.objects.create(
            user=recipient,
            actor=actor,
            task=task,
            notification_type=notification_type,
            title=title,
            message=message,
        )
    except Exception:
        return None
