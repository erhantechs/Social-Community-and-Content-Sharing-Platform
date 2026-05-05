"""Forms for signup, profile editing."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

from .models import Profile

User = get_user_model()


class SignUpForm(UserCreationForm):
    """Signup form — extends Django's built-in with email + first/last name + honeypot."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@example.com"}),
    )
    first_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"}),
    )
    last_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"}),
    )
    # Hidden honeypot — humans never see/fill it; bots auto-fill every field.
    # If anything ends up here we silently reject the signup.
    website_url = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "tabindex": "-1",
            "autocomplete": "off",
            "style": "position:absolute;left:-10000px;top:-10000px;height:0;width:0;",
            "aria-hidden": "true",
        }),
        label="",
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Username"}
        )
        self.fields["password1"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Confirm password"}
        )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_website_url(self):
        # Bots fill every field; humans never see this one.
        if self.cleaned_data.get("website_url"):
            raise ValidationError("Spam detected.")
        return ""

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Username"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Password"}
        )


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"]
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Another account already uses this email.")
        return email


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("display_name", "bio", "avatar", "cover", "location", "website", "interests")
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "How should we display you?"}),
            "bio": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Tell people about yourself…"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "City, Country"}),
            "website": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://"}),
            "interests": forms.CheckboxSelectMultiple(),
            "avatar": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "cover": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "size") and avatar.size > 5 * 1024 * 1024:
            raise ValidationError("Avatar must be smaller than 5 MB.")
        return avatar

    def clean_cover(self):
        cover = self.cleaned_data.get("cover")
        if cover and hasattr(cover, "size") and cover.size > 5 * 1024 * 1024:
            raise ValidationError("Cover image must be smaller than 5 MB.")
        return cover
