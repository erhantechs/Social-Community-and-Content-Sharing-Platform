"""Community forms."""
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Community, CommunityEvent


class CommunityForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = ("name", "description", "privacy", "avatar", "cover")
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Community name",
                "maxlength": 80,
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "What is this community about?",
                "maxlength": 500,
            }),
            "privacy": forms.Select(attrs={"class": "form-select"}),
            "avatar": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "cover": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }


class CommunityEventForm(forms.ModelForm):
    class Meta:
        model = CommunityEvent
        fields = ("title", "description", "location", "starts_at", "ends_at", "cover")
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "What's the event called?",
                "maxlength": 140,
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "What's it about? Who should come? Anything else members should know?",
                "maxlength": 2000,
            }),
            "location": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Online link, address, or city (optional)",
            }),
            "starts_at": forms.DateTimeInput(attrs={
                "class": "form-control",
                "type": "datetime-local",
            }),
            "ends_at": forms.DateTimeInput(attrs={
                "class": "form-control",
                "type": "datetime-local",
            }),
            "cover": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned = super().clean()
        starts = cleaned.get("starts_at")
        ends = cleaned.get("ends_at")
        if starts and starts < timezone.now():
            self.add_error("starts_at", "Start time can't be in the past.")
        if starts and ends and ends < starts:
            self.add_error("ends_at", "End time must be after the start.")
        return cleaned
