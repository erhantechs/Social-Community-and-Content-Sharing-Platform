from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/edit/", views.edit_profile_view, name="edit_profile"),
    path("profile/<str:username>/", views.profile_view, name="profile"),
    path("profile/<str:username>/followers/", views.followers_list, name="followers"),
    path("profile/<str:username>/following/", views.following_list, name="following"),
    path("follow/<str:username>/", views.toggle_follow, name="toggle_follow"),
    path("block/<str:username>/", views.toggle_block, name="toggle_block"),
    path("blocked/", views.blocked_list, name="blocked_list"),
    path("search/", views.search_users, name="search_users"),

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
]
