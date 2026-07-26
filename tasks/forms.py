from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from projects.models import Project
from teams.models import TeamMember

from .models import Comment, Task, TaskStatus, TaskSubmission


User = get_user_model()
ASSIGNABLE_ROLES = (
    TeamMember.Role.DEVELOPER,
    TeamMember.Role.TESTER,
)
TASK_EDITOR_ROLES = (
    TeamMember.Role.DEVELOPER,
    TeamMember.Role.TESTER,
)
VIEWER_ASSIGNEE_ERROR = "Користувача з роллю переглядача не можна призначити виконавцем задачі."


def get_available_projects(user):
    return Project.objects.filter(
        Q(team__owner=user) | Q(team__members__user=user, team__members__role__in=TASK_EDITOR_ROLES)
    ).distinct()


def get_team_users(project):
    return User.objects.filter(
        Q(owned_teams=project.team) | Q(team_memberships__team=project.team)
    ).distinct()


def get_assignable_team_users(project):
    return User.objects.filter(
        team_memberships__team=project.team,
        team_memberships__role__in=ASSIGNABLE_ROLES,
    ).distinct()


def get_available_team_users(project_queryset):
    return User.objects.filter(
        Q(owned_teams__projects__in=project_queryset)
        | Q(team_memberships__team__projects__in=project_queryset)
    ).distinct()


def get_assignable_users_for_projects(project_queryset):
    return User.objects.filter(
        team_memberships__team__projects__in=project_queryset,
        team_memberships__role__in=ASSIGNABLE_ROLES,
    ).distinct()


def set_assignee_choices(field, queryset):
    choices = [("", "Не призначено")]
    choices.extend((user.pk, field.label_from_instance(user)) for user in queryset)
    field.choices = choices


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["project", "title", "description", "status", "assignee", "priority", "deadline"]
        widgets = {
            "project": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "assignee": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "deadline": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(
        self,
        *args,
        user=None,
        selected_project=None,
        include_status=True,
        include_assignee=True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.user = user
        self.include_status = include_status
        self.include_assignee = include_assignee
        if not include_status:
            self.fields.pop("status", None)
        if not include_assignee:
            self.fields.pop("assignee", None)
        self.fields["priority"].choices = (
            (Task.Priority.HIGH, "Високий"),
            (Task.Priority.MEDIUM, "Середній"),
            (Task.Priority.LOW, "Низький"),
        )
        self.fields["deadline"].input_formats = ["%Y-%m-%d"]

        if user is None:
            return

        project_queryset = get_available_projects(user)
        self.fields["project"].queryset = project_queryset
        if self.include_assignee:
            self.fields["assignee"].empty_label = "Не призначено"

        project = selected_project or self.get_selected_project(project_queryset)
        if project:
            if self.include_status:
                self.fields["status"].queryset = TaskStatus.objects.filter(project=project)
            if self.include_assignee:
                assignable_users = get_assignable_team_users(project)
                self.fields["assignee"].queryset = assignable_users
                set_assignee_choices(self.fields["assignee"], assignable_users)
        else:
            if self.include_status:
                self.fields["status"].queryset = TaskStatus.objects.filter(project__in=project_queryset)
            if self.include_assignee:
                assignable_users = get_assignable_users_for_projects(project_queryset)
                self.fields["assignee"].queryset = assignable_users
                set_assignee_choices(self.fields["assignee"], assignable_users)

    def get_selected_project(self, project_queryset):
        project_id = self.data.get("project") or self.initial.get("project")
        if self.instance and self.instance.pk:
            return self.instance.project
        if isinstance(project_id, Project):
            return project_id
        if project_id:
            return project_queryset.filter(pk=project_id).first()
        return None

    def clean(self):
        cleaned_data = super().clean()
        project = cleaned_data.get("project")
        status = cleaned_data.get("status")
        assignee = cleaned_data.get("assignee")

        if project and status and status.project_id != project.id:
            self.add_error("status", "Статус має належати обраному проєкту.")

        if project and assignee:
            membership = assignee.team_memberships.filter(team=project.team).first()

            if not membership:
                self.add_error("assignee", "Виконавець має бути учасником команди проєкту.")
            elif membership and membership.role == TeamMember.Role.VIEWER:
                self.add_error("assignee", VIEWER_ASSIGNEE_ERROR)
            elif membership and membership.role not in ASSIGNABLE_ROLES:
                self.add_error("assignee", "Виконавець має бути розробником або тестувальником.")

        return cleaned_data


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Напишіть коментар...",
                }
            ),
        }


class TaskSubmissionForm(forms.ModelForm):
    class Meta:
        model = TaskSubmission
        fields = ["description", "result_link", "attachment"]
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Опишіть, що саме виконано у задачі.",
                }
            ),
            "result_link": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://example.com/result",
                }
            ),
            "attachment": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class ReturnForRevisionForm(forms.Form):
    reason = forms.CharField(
        required=False,
        label="Причина повернення",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Опишіть, що потрібно доопрацювати.",
            }
        ),
    )
