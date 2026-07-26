from django import forms
from teams.models import Team

from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["team", "name", "description"]
        widgets = {
            "team": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["team"].queryset = Team.objects.filter(owner=user)
            self.fields["team"].error_messages["invalid_choice"] = (
                "Ви не можете створювати проєкт у цій команді."
            )
