from django.contrib.auth import views as auth_views
from django.urls import path

from . import data_export, oauth, two_factor_views, views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("verify-email/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("verify-email/resend/", views.resend_verification_email, name="resend_verification_email"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("settings/", views.settings_view, name="settings"),
    path("onboarding/dismiss/", views.dismiss_onboarding, name="dismiss_onboarding"),
    path("profile/edit/", views.edit_profile_view, name="edit_profile"),
    path("profile/<str:username>/", views.profile_view, name="profile"),
    path("profile/<str:username>/followers/", views.followers_list, name="followers"),
    path("profile/<str:username>/following/", views.following_list, name="following"),
    path("follow/<str:username>/", views.toggle_follow, name="toggle_follow"),
    path("block/<str:username>/", views.toggle_block, name="toggle_block"),
    path("blocked/", views.blocked_list, name="blocked_list"),
    path("mute/<str:username>/", views.toggle_mute, name="toggle_mute"),
    path("muted/", views.muted_list, name="muted_list"),
    path("search/", views.search_users, name="search_users"),
    path("autocomplete/mentions/", views.mention_autocomplete, name="mention_autocomplete"),

    # Password reset (built-in)
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset.html"
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html"
    ), name="password_reset_done"),
    path("password-reset-confirm/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html"
    ), name="password_reset_confirm"),
    path("password-reset-complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html"
    ), name="password_reset_complete"),

    # ---------- 2FA ----------
    path("2fa/", two_factor_views.two_factor_status, name="two_factor_status"),
    path("2fa/setup/", two_factor_views.two_factor_setup, name="two_factor_setup"),
    path("2fa/disable/", two_factor_views.two_factor_disable, name="two_factor_disable"),
    path("2fa/codes/", two_factor_views.two_factor_backup_codes, name="two_factor_backup_codes"),
    path("2fa/codes/regenerate/", two_factor_views.two_factor_regenerate_codes, name="two_factor_regenerate"),
    path("2fa/verify/", two_factor_views.two_factor_verify, name="two_factor_verify"),

    # ---------- OAuth ----------
    path("oauth/<str:provider>/", oauth.oauth_start, name="oauth_start"),
    path("oauth/<str:provider>/callback/", oauth.oauth_callback, name="oauth_callback"),

    # ---------- GDPR data export ----------
    path("data-export/", data_export.data_export, name="data_export"),
]
