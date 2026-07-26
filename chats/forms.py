from django import forms

from teams.models import Team

from .models import ChatMessage, PrivateMessage
from .models import validate_chat_attachment


class ChatMessageForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ["text", "attachment"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Напишіть повідомлення...",
                }
            ),
            "attachment": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if attachment:
            validate_chat_attachment(attachment)
        return attachment


class ChatMessageEditForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }


class TeamMeetingForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["meeting_url"]
        widgets = {
            "meeting_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://meet.google.com/...",
                }
            ),
        }


class PrivateMessageForm(forms.ModelForm):
    class Meta:
        model = PrivateMessage
        fields = ["content", "attachment"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Напишіть приватне повідомлення...",
                }
            ),
            "attachment": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if attachment:
            validate_chat_attachment(attachment)
        return attachment


class PrivateMessageEditForm(forms.ModelForm):
    class Meta:
        model = PrivateMessage
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }
