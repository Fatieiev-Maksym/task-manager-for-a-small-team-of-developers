from django import forms
from django.contrib.auth import get_user_model

from .models import Team, TeamMember


User = get_user_model()


MEMBER_ROLE_CHOICES = (
    (TeamMember.Role.DEVELOPER, "Розробник"),
    (TeamMember.Role.TESTER, "Тестувальник"),
    (TeamMember.Role.VIEWER, "Переглядач"),
)


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }


class TeamMemberAddForm(forms.Form):
    user_identifier = forms.CharField(
        label="Логін або email",
        max_length=254,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    role = forms.ChoiceField(
        label="Роль",
        choices=MEMBER_ROLE_CHOICES,
        initial=TeamMember.Role.DEVELOPER,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, team=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        self.user = None

    def clean_user_identifier(self):
        identifier = self.cleaned_data["user_identifier"].strip()
        user = User.objects.filter(username__iexact=identifier).first()

        if user is None:
            users_by_email = User.objects.filter(email__iexact=identifier)
            if users_by_email.count() > 1:
                raise forms.ValidationError("Знайдено кілька користувачів з таким email.")
            user = users_by_email.first()

        if user is None:
            raise forms.ValidationError("Користувача з таким логіном або email не знайдено.")

        if user == self.team.owner:
            raise forms.ValidationError("Власник команди вже є учасником команди.")

        if TeamMember.objects.filter(team=self.team, user=user).exists():
            raise forms.ValidationError("Цей користувач уже є учасником команди.")

        self.user = user
        return identifier

    def save(self):
        return TeamMember.objects.create(
            team=self.team,
            user=self.user,
            role=self.cleaned_data["role"],
        )


class TeamMemberRoleForm(forms.ModelForm):
    role = forms.ChoiceField(
        label="Роль",
        choices=MEMBER_ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = TeamMember
        fields = ["role"]
