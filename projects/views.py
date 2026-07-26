from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from teams.models import Team, TeamMember
from tasks.sorting import apply_task_sort, get_task_sort_context

from .forms import ProjectForm
from .models import Project


def get_user_projects(user):
    return (
        Project.objects.filter(Q(team__owner=user) | Q(team__members__user=user))
        .select_related("team", "team__owner", "created_by")
        .distinct()
    )


def can_manage_project(user, project):
    return project.team.owner_id == user.id


def can_create_task_in_project(user, project):
    if project.team.owner_id == user.id:
        return True

    return project.team.members.filter(
        user=user,
        role__in=(TeamMember.Role.DEVELOPER, TeamMember.Role.TESTER),
    ).exists()


@login_required
def project_list(request):
    projects = get_user_projects(request.user)
    can_create_project = Team.objects.filter(owner=request.user).exists()
    return render(
        request,
        "projects/project_list.html",
        {"projects": projects, "can_create_project": can_create_project},
    )


@login_required
def project_create(request):
    owner_teams = Team.objects.filter(owner=request.user)
    if not owner_teams.exists():
        messages.error(request, "Ви не маєте команд, у яких можете створювати проєкти.")
        return redirect("projects:list")

    if request.method == "POST":
        form = ProjectForm(request.POST, user=request.user)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            return redirect("projects:detail", pk=project.pk)
    else:
        initial = {}
        team_id = request.GET.get("team")
        if team_id:
            team = owner_teams.filter(pk=team_id).first()
            if team:
                initial["team"] = team
        form = ProjectForm(user=request.user, initial=initial)

    return render(request, "projects/project_form.html", {"form": form, "title": "Створити проєкт"})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(get_user_projects(request.user), pk=pk)
    tasks = project.tasks.select_related("status", "assignee", "created_by")
    task_sort_context = get_task_sort_context(request, sort_param="task_sort", dir_param="task_dir")
    tasks = apply_task_sort(tasks, task_sort_context["sort"], task_sort_context["dir"])
    return render(
        request,
        "projects/project_detail.html",
        {
            "project": project,
            "can_manage": can_manage_project(request.user, project),
            "can_create_task": can_create_task_in_project(request.user, project),
            "tasks": tasks,
            "task_sort": task_sort_context["sort"],
            "task_dir": task_sort_context["dir"],
        },
    )


@login_required
def project_update(request, pk):
    project = get_object_or_404(get_user_projects(request.user), pk=pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("projects:detail", pk=project.pk)
    else:
        form = ProjectForm(instance=project, user=request.user)

    return render(
        request,
        "projects/project_form.html",
        {"form": form, "project": project, "title": "Редагувати проєкт"},
    )


@login_required
def project_delete(request, pk):
    project = get_object_or_404(get_user_projects(request.user), pk=pk)
    if not can_manage_project(request.user, project):
        raise PermissionDenied

    if request.method == "POST":
        project.delete()
        return redirect("projects:list")

    return render(request, "projects/project_confirm_delete.html", {"project": project})
