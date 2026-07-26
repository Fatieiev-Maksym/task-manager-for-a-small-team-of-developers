from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone

from notifications.models import Notification
from projects.models import Project
from tasks.models import Task
from teams.models import Team


STATUS_DONE = "Done"


def home(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")

    return render(request, "core/home.html")


@login_required
def dashboard(request):
    user = request.user
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    teams = Team.objects.filter(Q(owner=user) | Q(members__user=user)).distinct()
    projects = Project.objects.filter(Q(team__owner=user) | Q(team__members__user=user)).distinct()
    tasks = (
        Task.objects.filter(Q(project__team__owner=user) | Q(project__team__members__user=user))
        .select_related("project", "status", "assignee")
        .distinct()
    )

    deadline_tasks = list(tasks.exclude(deadline__isnull=True).order_by("deadline", "updated_at")[:5])
    for task in deadline_tasks:
        task.deadline_label = ""
        task.deadline_label_class = ""

        if task.status.name != STATUS_DONE:
            if task.deadline < today:
                task.deadline_label = "Прострочено"
                task.deadline_label_class = "deadline-overdue"
            elif task.deadline == today:
                task.deadline_label = "Сьогодні"
                task.deadline_label_class = "deadline-today"
            elif task.deadline == tomorrow:
                task.deadline_label = "Завтра"
                task.deadline_label_class = "deadline-tomorrow"

    context = {
        "team_count": teams.count(),
        "project_count": projects.count(),
        "task_count": tasks.count(),
        "high_priority_count": tasks.filter(priority=Task.Priority.HIGH).count(),
        "todo_count": tasks.filter(status__name="To Do").count(),
        "in_progress_count": tasks.filter(status__name="In Progress").count(),
        "in_review_count": tasks.filter(status__name="In Review").count(),
        "done_count": tasks.filter(status__name="Done").count(),
        "unread_notification_count": Notification.objects.filter(user=user, is_read=False).count(),
        "upcoming_deadlines": deadline_tasks,
        "recent_tasks": tasks.order_by("-updated_at", "-created_at")[:5],
    }
    return render(request, "core/dashboard.html", context)
