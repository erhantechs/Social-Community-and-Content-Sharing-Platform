"""Post and comment forms."""
from django import forms
from django.core.exceptions import ValidationError

from .models import Comment, Post, Story

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_SIZE = 8 * 1024 * 1024  # 8 MB


def _validate_image(image):
    if not image:
        return image
    content_type = getattr(image, "content_type", None)
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError("Image must be a JPG, PNG, GIF, or WebP file.")
    if hasattr(image, "size") and image.size > MAX_IMAGE_SIZE:
        raise ValidationError("Image must be smaller than 8 MB.")
    return image


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ("body", "image", "location", "visibility", "interests")
        widgets = {
            "body": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Share something with your community…",
            }),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Where was this? (optional)",
            }),
            "visibility": forms.Select(attrs={"class": "form-select"}),
            "interests": forms.CheckboxSelectMultiple(),
        }

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise ValidationError("Posts can't be empty.")
        return body

    def clean_image(self):
        return _validate_image(self.cleaned_data.get("image"))


class QuickPostForm(forms.ModelForm):
    """The small 'Share something' composer at the bottom of the feed."""

    class Meta:
        model = Post
        fields = ("body", "image", "location", "visibility")
        widgets = {
            "body": forms.TextInput(attrs={
                "class": "share-input",
                "placeholder": "Share something…",
                "autocomplete": "off",
            }),
            "image": forms.ClearableFileInput(),
            "location": forms.TextInput(),
            "visibility": forms.Select(),
        }

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise ValidationError("Posts can't be empty.")
        return body

    def clean_image(self):
        return _validate_image(self.cleaned_data.get("image"))


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ("body",)
        widgets = {
            "body": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Write a comment…",
            }),
        }

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise ValidationError("Comment can't be empty.")
        return body


class StoryForm(forms.ModelForm):
    class Meta:
        model = Story
        fields = ("image", "caption")
        widgets = {
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "caption": forms.TextInput(attrs={"class": "form-control", "placeholder": "Caption (optional)"}),
        }

    def clean_image(self):
        return _validate_image(self.cleaned_data.get("image"))
