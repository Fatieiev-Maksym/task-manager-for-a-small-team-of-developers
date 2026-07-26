from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Case, F, IntegerField, ProtectedError, Q, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import TeamForm, TeamMemberAddForm, TeamMemberRoleForm
from .models import Team, TeamMember


ROLE_LABELS = {
    TeamMember.Role.OWNER: "Керівник команди",
    TeamMember.Role.DEVELOPER: "Розробник",
    TeamMember.Role.TESTER: "Тестувальник",
    TeamMember.Role.VIEWER: "Переглядач",
}

ALLOWED_MEMBER_SORTS = {"user", "email", "role", "joined"}

ROLE_ORDER = (
    (TeamMember.Role.OWNER, 0),
    (TeamMember.Role.DEVELOPER, 1),
    (TeamMember.Role.TESTER, 2),
    (TeamMember.Role.VIEWER, 3),
)

LEAVABLE_ROLES = (
    TeamMember.Role.DEVELOPER,
    TeamMember.Role.TESTER,
    TeamMember.Role.VIEWER,
)


def get_user_teams(user):
    return Team.objects.filter(Q(owner=user) | Q(members__user=user)).select_related("owner").distinct()


def get_sort_direction(direction):
    return "desc" if direction == "desc" else "asc"


def get_member_sort_context(request):
    sort = request.GET.get("sort")
    direction = get_sort_direction(request.GET.get("dir"))
    if sort not in ALLOWED_MEMBER_SORTS:
        sort = ""
    return {"sort": sort, "dir": direction}


def sort_expression(field_name, descending=False, nulls_last=False):
    expression = F(field_name)
    if descending:
        if nulls_last:
            return expression.desc(nulls_last=True)
        return expression.desc()
    if nulls_last:
        return expression.asc(nulls_last=True)
    return expression.asc()


def apply_member_sort(queryset, sort, direction):
    if sort not in ALLOWED_MEMBER_SORTS:
        return queryset

    descending = direction == "desc"

    if sort == "user":
        return queryset.order_by(sort_expression("user__username", descending), "pk")
    if sort == "email":
        email_empty = Case(
            When(user__email="", then=1),
            default=0,
            output_field=IntegerField(),
        )
        return queryset.annotate(_email_empty=email_empty).order_by(
            "_email_empty",
            sort_expression("user__email", descending),
            "pk",
        )
    if sort == "role":
        role_order = Case(
            *[When(role=role, then=position) for role, position in ROLE_ORDER],
            default=99,
            output_field=IntegerField(),
        )
        order_field = "-_role_order" if descending else "_role_order"
        return queryset.annotate(_role_order=role_order).order_by(order_field, "user__username", "pk")
    if sort == "joined":
        return queryset.order_by(sort_expression("joined_at", descending), "pk")

    return queryset


@login_required
def team_list(request):
    teams = get_user_teams(request.user)
    return render(request, "teams/team_list.html", {"teams": teams})


@login_required
def team_create(request):
    if request.method == "POST":
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save(commit=False)
            team.owner = request.user
            team.save()
            TeamMember.objects.create(team=team, user=request.user, role=TeamMember.Role.OWNER)
            return redirect("teams:detail", pk=team.pk)
    else:
        form = TeamForm()

    return render(request, "teams/team_form.html", {"form": form, "title": "Створити команду"})


@login_required
def team_detail(request, pk):
    team = get_object_or_404(get_user_teams(request.user), pk=pk)
    current_member = team.members.filter(user=request.user).first()
    can_leave_team = (
        current_member is not None
        and team.owner_id != request.user.id
        and current_member.role in LEAVABLE_ROLES
    )
    sort_context = get_member_sort_context(request)
    member_queryset = apply_member_sort(
        team.members.select_related("user"),
        sort_context["sort"],
        sort_context["dir"],
    )
    members = []
    for member in member_queryset:
        member.role_label = ROLE_LABELS.get(member.role, member.get_role_display())
        members.append(member)
    return render(
        request,
        "teams/team_detail.html",
        {
            "team": team,
            "members": members,
            "can_leave_team": can_leave_team,
            "sort": sort_context["sort"],
            "dir": sort_context["dir"],
        },
    )


@login_required
@require_POST
def team_leave(request, pk):
    team = get_object_or_404(Team, pk=pk)
    member = team.members.filter(user=request.user).first()

    if team.owner_id == request.user.id or (member and member.role == TeamMember.Role.OWNER):
        messages.error(request, "Керівник команди не може покинути власну команду.")
        return redirect("teams:detail", pk=team.pk)

    if member is None:
        messages.error(request, "Ви не є учасником цієї команди.")
        return redirect("teams:list")

    if member.role not in LEAVABLE_ROLES:
        raise PermissionDenied

    member.delete()
    messages.success(request, "Ви вийшли з команди.")
    return redirect("teams:list")


@login_required
def team_update(request, pk):
    team = get_object_or_404(Team, pk=pk, owner=request.user)

    if request.method == "POST":
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            return redirect("teams:detail", pk=team.pk)
    else:
        form = TeamForm(instance=team)

    return render(request, "teams/team_form.html", {"form": form, "team": team, "title": "Редагувати команду"})


@login_required
def team_delete(request, pk):
    team = get_object_or_404(Team, pk=pk, owner=request.user)
    has_projects = team.projects.exists()

    if request.method == "POST":
        if has_projects:
            messages.error(
                request,
                "Неможливо видалити команду, оскільки до неї прив’язані проєкти. "
                "Спочатку видаліть або перенесіть проєкти цієї команди.",
            )
            return redirect("teams:detail", pk=team.pk)

        try:
            team.delete()
        except ProtectedError:
            messages.error(request, "Команду неможливо видалити, оскільки вона має пов’язані дані.")
            return redirect("teams:detail", pk=team.pk)

        return redirect("teams:list")

    return render(request, "teams/team_confirm_delete.html", {"team": team, "has_projects": has_projects})


@login_required
def team_member_add(request, pk):
    team = get_object_or_404(Team, pk=pk, owner=request.user)

    if request.method == "POST":
        form = TeamMemberAddForm(request.POST, team=team)
        if form.is_valid():
            form.save()
            return redirect("teams:detail", pk=team.pk)
    else:
        form = TeamMemberAddForm(team=team)

    return render(
        request,
        "teams/team_member_form.html",
        {"form": form, "team": team, "title": "Додати учасника"},
    )


@login_required
def team_member_edit(request, pk, member_pk):
    team = get_object_or_404(Team, pk=pk, owner=request.user)
    member = get_object_or_404(TeamMember.objects.select_related("user", "team"), pk=member_pk, team=team)

    if member.user_id == team.owner_id:
        raise PermissionDenied

    if request.method == "POST":
        form = TeamMemberRoleForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            return redirect("teams:detail", pk=team.pk)
    else:
        form = TeamMemberRoleForm(instance=member)

    return render(
        request,
        "teams/team_member_form.html",
        {"form": form, "team": team, "member": member, "title": "Змінити роль учасника"},
    )


@login_required
def team_member_delete(request, pk, member_pk):
    team = get_object_or_404(Team, pk=pk, owner=request.user)
    member = get_object_or_404(TeamMember.objects.select_related("user", "team"), pk=member_pk, team=team)

    if member.user_id == team.owner_id:
        raise PermissionDenied

    if request.method == "POST":
        member.delete()
        return redirect("teams:detail", pk=team.pk)

    return render(request, "teams/team_member_confirm_delete.html", {"team": team, "member": member})
