"""API URL routing — `/api/...`"""
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from . import views

app_name = "api"

router = DefaultRouter()
router.register(r"posts", views.PostViewSet, basename="post")
router.register(r"comments", views.CommentViewSet, basename="comment")

urlpatterns = [
    path("", include(router.urls)),
    path("users/<str:username>/", views.ProfileDetail.as_view(), name="user_detail"),
    path("users/<str:username>/follow/", views.toggle_follow, name="user_follow"),
    path("auth/token/", obtain_auth_token, name="obtain_token"),

    # OpenAPI / Swagger / ReDoc
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="api:schema"), name="redoc"),
]
