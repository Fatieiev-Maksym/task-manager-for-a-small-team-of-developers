from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from chats.models import validate_chat_attachment
from notifications.models import Notification
from notifications.utils import create_notification
from teams.models import TeamMember

from .forms import CommentForm, ReturnForRevisionForm, TaskForm, TaskSubmissionForm, get_available_projects
from .models import (
    Comment,
    Task,
    TaskAttachment,
    TaskCommentAttachment,
    TaskStatus,
    TaskSubmission,
    validate_task_attachment,
)
from .sorting import apply_task_sort, get_task_sort_context


User = get_user_model()

STATUS_TODO = "To Do"
STATUS_IN_PROGRESS = "In Progress"
STATUS_IN_REVIEW = "In Review"
STATUS_DONE = "Done"

DEFAULT_STATUSES = (
    (STATUS_TODO, 1),
    (STATUS_IN_PROGRESS, 2),
    (STATUS_IN_REVIEW, 3),
    (STATUS_DONE, 4),
)

TASK_EDITOR_ROLES = (
    TeamMember.Role.DEVELOPER,
    TeamMember.Role.TESTER,
)


def get_user_tasks(user):
    return (
        Task.objects.filter(Q(project__team__owner=user) | Q(project__team__members__user=user))
        .select_related("project", "project__team", "project__team__owner", "status", "assignee", "created_by")
        .distinct()
    )


def ensure_default_statuses(project):
    for name, order in DEFAULT_STATUSES:
        TaskStatus.objects.get_or_create(project=project, name=name, defaults={"order": order})


def ensure_default_statuses_for_projects(projects):
    for project in projects:
        ensure_default_statuses(project)


def get_selected_project(request):
    project_id = request.POST.get("project") if request.method == "POST" else request.GET.get("project")
    if not project_id:
        return None
    return get_object_or_404(get_available_projects(request.user), pk=project_id)


def get_project_status(project, name):
    ensure_default_statuses(project)
    return TaskStatus.objects.get(project=project, name=name)


def get_team_member_role(user, team):
    if team.owner_id == user.id:
        return TeamMember.Role.OWNER

    membership = team.members.filter(user=user).first()
    if membership:
        return membership.role

    return None


def can_work_with_task(user, task):
    role = get_team_member_role(user, task.project.team)
    return role in (TeamMember.Role.OWNER, *TASK_EDITOR_ROLES)


def can_manage_task(user, task):
    role = get_team_member_role(user, task.project.team)
    if role == TeamMember.Role.OWNER:
        return True

    return role in TASK_EDITOR_ROLES and task.created_by_id == user.id


def can_change_task_assignee(user, task):
    return get_team_member_role(user, task.project.team) == TeamMember.Role.OWNER


def can_delete_task(user, task):
    return can_manage_task(user, task)


def can_delete_comment(user, comment):
    if comment.task.project.team.owner_id == user.id:
        return True

    return comment.author_id == user.id and can_work_with_task(user, comment.task)


def can_comment_task(user, task):
    return can_work_with_task(user, task)


def can_start_task(user, task):
    if task.assignee_id != user.id:
        return False
    if not can_work_with_task(user, task):
        return False
    return task.status.name == STATUS_TODO


def can_submit_task(user, task):
    if task.assignee_id != user.id:
        return False
    if not can_work_with_task(user, task):
        return False
    return task.status.name == STATUS_IN_PROGRESS


def can_review_task(user, task):
    return task.project.team.owner_id == user.id and task.status.name == STATUS_IN_REVIEW


def format_task_deadline(task):
    if task.deadline:
        return f" Дедлайн: {task.deadline.strftime('%d.%m.%Y')}."
    return ""


def notify_assignee(task, actor, notification_type, title, message):
    create_notification(
        recipient=task.assignee,
        actor=actor,
        task=task,
        notification_type=notification_type,
        title=title,
        message=message,
    )


def notify_task_owner(task, actor, notification_type, title, message):
    create_notification(
        recipient=task.project.team.owner,
        actor=actor,
        task=task,
        notification_type=notification_type,
        title=title,
        message=message,
    )


def notify_task_reviewers(task, submitted_by):
    team = task.project.team
    owner_ids = {team.owner_id}
    owner_ids.update(
        team.members.filter(role=TeamMember.Role.OWNER).values_list("user_id", flat=True)
    )
    owner_ids.discard(submitted_by.id)

    for owner in User.objects.filter(pk__in=owner_ids):
        create_notification(
            recipient=owner,
            actor=submitted_by,
            task=task,
            notification_type=Notification.Type.TASK_SUBMITTED,
            title="Задачу надіслано на перевірку",
            message=f'Виконавець {submitted_by.username} надіслав результат за задачею "{task.title}" на перевірку.',
        )


def create_task_assignment_notification(task, user, actor, title, is_new=True):
    task_label = "нову задачу" if is_new else "задачу"
    create_notification(
        recipient=user,
        actor=actor,
        task=task,
        notification_type=Notification.Type.TASK_ASSIGNED,
        title=title,
        message=f'Вам призначено {task_label}: "{task.title}".{format_task_deadline(task)}',
    )


def validate_comment_attachments(comment_form, uploaded_files):
    for uploaded_file in uploaded_files:
        try:
            validate_chat_attachment(uploaded_file)
        except ValidationError as error:
            comment_form.add_error(None, error)


def validate_task_attachments(form, uploaded_files):
    for uploaded_file in uploaded_files:
        try:
            validate_task_attachment(uploaded_file)
        except ValidationError as error:
            form.add_error(None, error)


def save_task_attachments(task, uploaded_files, user):
    for uploaded_file in uploaded_files:
        TaskAttachment.objects.create(
            task=task,
            file=uploaded_file,
            uploaded_by=user,
            original_name=uploaded_file.name[:255],
        )


@login_required
def task_list(request):
    tasks = get_user_tasks(request.user)
    sort_context = get_task_sort_context(request)
    tasks = apply_task_sort(tasks, sort_context["sort"], sort_context["dir"])
    can_create_task = get_available_projects(request.user).exists()
    return render(
        request,
        "tasks/task_list.html",
        {
            "tasks": tasks,
            "can_create_task": can_create_task,
            "sort": sort_context["sort"],
            "dir": sort_context["dir"],
        },
    )


@login_required
def task_create(request):
    available_projects = get_available_projects(request.user).select_related("team")
    if not available_projects.exists():
        messages.error(request, "У вас немає проєктів, у яких можна створювати задачі.")
        return redirect("tasks:list")

    ensure_default_statuses_for_projects(available_projects)
    selected_project = get_selected_project(request)

    if request.method == "POST":
        uploaded_files = request.FILES.getlist("attachments")
        form = TaskForm(
            request.POST,
            user=request.user,
            selected_project=selected_project,
            include_status=False,
            include_assignee=True,
        )
        if form.is_valid():
            validate_task_attachments(form, uploaded_files)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.status = get_project_status(task.project, STATUS_TODO)
            task.save()
            save_task_attachments(task, uploaded_files, request.user)
            if task.assignee and task.assignee_id != request.user.id:
                create_task_assignment_notification(task, task.assignee, request.user, "Нова задача")
            return redirect("tasks:detail", pk=task.pk)
    else:
        initial = {}
        if selected_project:
            initial = {"project": selected_project}
        form = TaskForm(
            user=request.user,
            selected_project=selected_project,
            initial=initial,
            include_status=False,
            include_assignee=True,
        )

    return render(
        request,
        "tasks/task_form.html",
        {
            "form": form,
            "title": "Створити задачу",
            "selected_project": selected_project,
            "status_hint": STATUS_TODO,
        },
    )


@login_required
def task_detail(request, pk):
    task = get_object_or_404(get_user_tasks(request.user), pk=pk)
    if request.method == "POST":
        if not can_comment_task(request.user, task):
            raise PermissionDenied

        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            uploaded_files = request.FILES.getlist("attachments")
            validate_comment_attachments(comment_form, uploaded_files)

        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            for uploaded_file in request.FILES.getlist("attachments"):
                TaskCommentAttachment.objects.create(comment=comment, file=uploaded_file)
            if task.assignee_id == request.user.id:
                notify_task_owner(
                    task,
                    request.user,
                    Notification.Type.TASK_COMMENTED,
                    "Новий коментар до задачі",
                    f'Користувач {request.user.username} додав коментар до задачі "{task.title}".',
                )
            return redirect("tasks:detail", pk=task.pk)
    else:
        comment_form = CommentForm()

    comments = task.comments.select_related("author").prefetch_related("attachments").order_by("created_at")
    for comment in comments:
        comment.can_delete = can_delete_comment(request.user, comment)
    submissions = task.submissions.select_related("submitted_by")
    attachments = task.attachments.select_related("uploaded_by")

    return render(
        request,
        "tasks/task_detail.html",
        {
            "task": task,
            "can_manage": can_manage_task(request.user, task),
            "can_delete": can_delete_task(request.user, task),
            "can_comment": can_comment_task(request.user, task),
            "can_start": can_start_task(request.user, task),
            "can_submit": can_submit_task(request.user, task),
            "can_review": can_review_task(request.user, task),
            "comments": comments,
            "comment_form": comment_form,
            "submissions": submissions,
            "attachments": attachments,
            "return_form": ReturnForRevisionForm(),
        },
    )


@login_required
def task_update(request, pk):
    task = get_object_or_404(get_user_tasks(request.user), pk=pk)
    if not can_manage_task(request.user, task):
        raise PermissionDenied

    ensure_default_statuses(task.project)
    old_values = {
        "title": task.title,
        "description": task.description,
        "deadline": task.deadline,
        "assignee_id": task.assignee_id,
        "priority": task.priority,
    }
    can_change_assignee = can_change_task_assignee(request.user, task)

    if request.method == "POST":
        selected_project = get_selected_project(request)
        if selected_project:
            ensure_default_statuses(selected_project)
        uploaded_files = request.FILES.getlist("attachments")
        form = TaskForm(
            request.POST,
            instance=task,
            user=request.user,
            selected_project=selected_project,
            include_status=False,
            include_assignee=can_change_assignee,
        )
        if form.is_valid():
            validate_task_attachments(form, uploaded_files)
        if form.is_valid():
            task = form.save()
            save_task_attachments(task, uploaded_files, request.user)
            task_was_updated = any(
                old_values[field] != getattr(task, field)
                for field in ("title", "description", "deadline", "priority")
            )
            if (
                task.assignee
                and task.assignee_id != old_values["assignee_id"]
                and task.assignee_id != request.user.id
            ):
                create_task_assignment_notification(
                    task,
                    task.assignee,
                    request.user,
                    "Задачу призначено вам",
                    is_new=False,
                )
            elif task.assignee and task.assignee_id != request.user.id and task_was_updated:
                create_notification(
                    recipient=task.assignee,
                    actor=request.user,
                    task=task,
                    notification_type=Notification.Type.TASK_UPDATED,
                    title="Задачу оновлено",
                    message=f'Задачу "{task.title}" було оновлено.',
                )
            return redirect("tasks:detail", pk=task.pk)
    else:
        form = TaskForm(
            instance=task,
            user=request.user,
            selected_project=task.project,
            include_status=False,
            include_assignee=can_change_assignee,
        )

    return render(
        request,
        "tasks/task_form.html",
        {
            "form": form,
            "task": task,
            "title": "Редагувати задачу",
            "selected_project": task.project,
            "status_hint": task.status.name,
        },
    )


@login_required
def task_delete(request, pk):
    task = get_object_or_404(get_user_tasks(request.user), pk=pk)
    if not can_delete_task(request.user, task):
        raise PermissionDenied

    if request.method == "POST":
        task.delete()
        return redirect("tasks:list")

    return render(request, "tasks/task_confirm_delete.html", {"task": task})


@login_required
@require_POST
def task_start(request, pk):
    task = get_object_or_404(get_user_tasks(request.user), pk=pk)
    if not can_start_task(request.user, task):
        raise PermissionDenied

    task.status = get_project_status(task.project, STATUS_IN_PROGRESS)
    task.save(update_fields=["status", "updated_at"])
    notify_task_owner(
        task,
        request.user,
        Notification.Type.TASK_STARTED,
        "Задачу взято в роботу",
        f'Виконавець {request.user.username} взяв задачу "{task.title}" в роботу.',
    )
    messages.success(request, "Задачу взято в роботу.")
    return redirect("tasks:detail", pk=task.pk)


@login_required
def task_submit(request, pk):
    task = get_object_or_404(get_user_tasks(request.user), pk=pk)
    if not can_submit_task(request.user, task):
        raise PermissionDenied

    if request.method == "POST":
        form = TaskSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.task = task
            submission.submitted_by = request.user
            submission.save()

            task.status = get_project_status(task.project, STATUS_IN_REVIEW)
            task.save(update_fields=["status", "updated_at"])
            notify_task_reviewers(task, request.user)

            messages.success(request, "Результат виконання задачі надіслано на перевірку.")
            return redirect("tasks:detail", pk=task.pk)
    else:
        form = TaskSubmissionForm()

    return render(request, "tasks/task_submission_form.html", {"task": task, "form": form})


@login_required
def submission_download(request, pk):
    submission = get_object_or_404(
        TaskSubmission.objects.select_related("task", "task__project", "task__project__team", "submitted_by"),
        pk=pk,
        task__in=get_user_tasks(request.user),
    )

    if not submission.attachment:
        raise Http404

    filename = Path(submission.attachment.name).name
    return FileResponse(submission.attachment.open("rb"), as_attachment=True, filename=filename)


@login_required
def comment_attachment_download(request, pk):
    attachment = get_object_or_404(
        TaskCommentAttachment.objects.select_related(
            "comment",
            "comment__task",
            "comment__task__project",
            "comment__task__project__team",
        ),
        pk=pk,
        comment__task__in=get_user_tasks(request.user),
    )

    use_thumbnail = request.GET.get("thumbnail") == "1" and attachment.is_image_attachment
    file_field = attachment.file
    if use_thumbnail:
        if not attachment.thumbnail:
            attachment.create_thumbnail()
            attachment.refresh_from_db(fields=["thumbnail"])
        if attachment.thumbnail:
            file_field = attachment.thumbnail

    filename = Path(file_field.name).name
    force_download = request.GET.get("download") == "1"
    return FileResponse(
        file_field.open("rb"),
        as_attachment=force_download or not attachment.is_image_attachment,
        filename=filename,
    )


@login_required
def task_attachment_download(request, pk):
    attachment = get_object_or_404(
        TaskAttachment.objects.select_related(
            "task",
            "task__project",
            "task__project__team",
            "uploaded_by",
        ),
        pk=pk,
        task__in=get_user_tasks(request.user),
    )

    if not attachment.file:
        raise Http404

    force_download = request.GET.get("download") == "1"
    return FileResponse(
        attachment.file.open("rb"),
        as_attachment=force_download or not attachment.is_image_attachment,
        filename=attachment.file_name,
    )


@login_required
@require_POST
def task_accept(request, pk):
    task = get_object_or_404(get_user_tasks(request.user), pk=pk)
    if not can_review_task(request.user, task):
        raise PermissionDenied

    task.status = get_project_status(task.project, STATUS_DONE)
    task.save(update_fields=["status", "updated_at"])
    notify_assignee(
        task,
        request.user,
        Notification.Type.TASK_APPROVED,
        "Виконання задачі прийнято",
        f'Ваш результат за задачею "{task.title}" затверджено. Задачу завершено.',
    )
    messages.success(request, "Виконання задачі прийнято.")
    return redirect("tasks:detail", pk=task.pk)


@login_required
@require_POST
def task_return_for_revision(request, pk):
    task = get_object_or_404(get_user_tasks(request.user), pk=pk)
    if not can_review_task(request.user, task):
        raise PermissionDenied

    form = ReturnForRevisionForm(request.POST)
    if form.is_valid():
        reason = form.cleaned_data.get("reason", "").strip()
        task.status = get_project_status(task.project, STATUS_IN_PROGRESS)
        task.save(update_fields=["status", "updated_at"])

        if reason:
            Comment.objects.create(
                task=task,
                author=request.user,
                text=f"Задачу повернено на доопрацювання: {reason}",
            )

        notify_assignee(
            task,
            request.user,
            Notification.Type.TASK_REJECTED,
            "Задачу повернено на доопрацювання",
            f'Результат за задачею "{task.title}" відхилено. Задачу повернено на доопрацювання.',
        )
        messages.success(request, "Задачу повернено на доопрацювання.")

    return redirect("tasks:detail", pk=task.pk)


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(
        Comment.objects.select_related("task", "task__project", "task__project__team", "author"),
        pk=pk,
        task__in=get_user_tasks(request.user),
    )
    task_pk = comment.task_id

    if not can_delete_comment(request.user, comment):
        raise PermissionDenied

    comment.delete()
    return redirect("tasks:detail", pk=task_pk)
