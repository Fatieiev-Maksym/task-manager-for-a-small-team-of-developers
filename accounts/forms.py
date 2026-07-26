from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False, max_length=150)
    last_name = forms.CharField(required=False, max_length=150)

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Логін"
        self.fields["username"].help_text = ""
        self.fields["email"].label = "Email"
        self.fields["first_name"].label = "Ім'я"
        self.fields["last_name"].label = "Прізвище"
        self.fields["password1"].label = "Пароль"
        self.fields["password1"].help_text = (
            "Пароль має містити щонайменше 8 символів, і не складатися лише з цифр"
            ""
        )
        self.fields["password2"].label = "Підтвердження пароля"
        self.fields["password2"].help_text = "Повторіть пароль для підтвердження"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Користувач з таким email вже існує.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={"class": "form-control"}))

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        user_id = self.instance.pk
        if User.objects.filter(email__iexact=email).exclude(pk=user_id).exists():
            raise forms.ValidationError("Цей email вже використовується іншим користувачем.")
        return email
