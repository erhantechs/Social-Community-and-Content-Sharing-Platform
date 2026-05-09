"""Post and comment forms."""
from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Comment, Poll, PollOption, Post, PostDraft, Story


class RepostForm(forms.ModelForm):
    """Form for a quote-repost. `body` is optional (pure repost has no body)."""

    class Meta:
        model = Post
        fields = ("body", "visibility")
        widgets = {
            "body": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Add a comment (optional)…",
                "maxlength": 1000,
            }),
            "visibility": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The model field is non-blank, but a pure repost is valid without a body.
        self.fields["body"].required = False

    def clean_body(self):
        return (self.cleaned_data.get("body") or "").strip()

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
        fields = ("body", "image", "location", "visibility", "interests", "community")
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
            "community": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit the community dropdown to communities the user is a member of.
        if user is not None and user.is_authenticated:
            from communities.models import Community, CommunityMember
            self.fields["community"].queryset = Community.objects.filter(
                memberships__user=user,
                memberships__status=CommunityMember.ACTIVE,
            ).order_by("name")
            self.fields["community"].empty_label = "— My feed (no community) —"
        else:
            from communities.models import Community
            self.fields["community"].queryset = Community.objects.none()

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


class PollCreateForm(forms.Form):
    """Bound to an existing Post — adds a Poll + 2-4 options.

    Submitted alongside PostForm/QuickPostForm via separate fields:
        poll_question, poll_option_1..4, poll_duration_hours, poll_multiple
    """

    DURATIONS = [
        (1, "1 hour"),
        (6, "6 hours"),
        (24, "1 day"),
        (72, "3 days"),
        (168, "1 week"),
    ]

    question = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ask a question (optional)"}),
    )
    option_1 = forms.CharField(max_length=120, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Option 1"}))
    option_2 = forms.CharField(max_length=120, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Option 2"}))
    option_3 = forms.CharField(max_length=120, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Option 3 (optional)"}))
    option_4 = forms.CharField(max_length=120, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Option 4 (optional)"}))
    duration_hours = forms.TypedChoiceField(
        choices=DURATIONS, coerce=int, initial=24, required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    multiple_choice = forms.BooleanField(
        required=False, label="Allow multiple answers",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean(self):
        cleaned = super().clean()
        opts = [
            (cleaned.get("option_1") or "").strip(),
            (cleaned.get("option_2") or "").strip(),
            (cleaned.get("option_3") or "").strip(),
            (cleaned.get("option_4") or "").strip(),
        ]
        non_empty = [o for o in opts if o]
        if non_empty and len(non_empty) < 2:
            raise ValidationError("A poll needs at least 2 options.")
        if non_empty and len(set(non_empty)) != len(non_empty):
            raise ValidationError("Poll options must be unique.")
        cleaned["_options"] = non_empty
        return cleaned

    @property
    def has_poll(self):
        return bool((self.cleaned_data or {}).get("_options"))

    def attach_to(self, post):
        """Create the Poll + PollOption rows tied to `post`. No-op if empty."""
        opts = (self.cleaned_data or {}).get("_options") or []
        if not opts:
            return None
        hours = self.cleaned_data.get("duration_hours") or 24
        poll = Poll.objects.create(
            post=post,
            question=self.cleaned_data.get("question", "").strip(),
            multiple_choice=self.cleaned_data.get("multiple_choice", False),
            closes_at=timezone.now() + timedelta(hours=int(hours)),
        )
        for idx, text in enumerate(opts):
            PollOption.objects.create(poll=poll, text=text, order=idx)
        return poll


class DraftForm(forms.ModelForm):
    """Save-as-draft form. Body can be empty (unlike Post)."""

    class Meta:
        model = PostDraft
        fields = ("body", "image", "location", "visibility", "community")
        widgets = {
            "body": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Jot down your idea — you can publish it later.",
            }),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "visibility": forms.Select(attrs={"class": "form-select"}),
            "community": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None and user.is_authenticated:
            from communities.models import Community, CommunityMember
            self.fields["community"].queryset = Community.objects.filter(
                memberships__user=user,
                memberships__status=CommunityMember.ACTIVE,
            ).order_by("name")
            self.fields["community"].empty_label = "— My feed (no community) —"
        else:
            from communities.models import Community
            self.fields["community"].queryset = Community.objects.none()

    def clean_image(self):
        return _validate_image(self.cleaned_data.get("image"))


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
