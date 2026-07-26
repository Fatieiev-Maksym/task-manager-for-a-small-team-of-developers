from django.contrib.auth import get_user_model
from django.db import models


User = get_user_model()


class Team(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_teams")
    meeting_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TeamMember(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Керівник команди"
        DEVELOPER = "developer", "Розробник"
        TESTER = "tester", "Тестувальник"
        VIEWER = "viewer", "Переглядач"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="team_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.DEVELOPER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("team", "user")
        ordering = ["team__name", "user__username"]

    def __str__(self):
        return f"{self.user} - {self.team}"
