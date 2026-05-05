from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("with/<str:username>/", views.open_conversation, name="open_with"),
    path("<int:pk>/", views.thread, name="thread"),
]
