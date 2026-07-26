from django import template


register = template.Library()


TASK_STATUS_LABELS_UK = {
    "To Do": "До виконання",
    "To do": "До виконання",
    "In Progress": "У роботі",
    "In Review": "На перевірці",
    "Done": "Виконано",
}


TASK_PRIORITY_LABELS_UK = {
    "high": "Високий",
    "High": "Високий",
    "medium": "Середній",
    "Medium": "Середній",
    "low": "Низький",
    "Low": "Низький",
}


@register.filter
def task_status_uk(status):
    if not status:
        return ""

    status_name = getattr(status, "name", status)
    return TASK_STATUS_LABELS_UK.get(str(status_name), status_name)


@register.filter
def task_priority_uk(priority):
    if not priority:
        return ""

    return TASK_PRIORITY_LABELS_UK.get(str(priority), priority)
