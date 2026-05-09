from django.urls import path

from . import views

app_name = "communities"

urlpatterns = [
    path("", views.community_list, name="list"),
    path("new/", views.community_create, name="create"),
    path("<slug:slug>/", views.community_detail, name="detail"),
    path("<slug:slug>/join/", views.community_join, name="join"),
    path("<slug:slug>/leave/", views.community_leave, name="leave"),
    path("<slug:slug>/manage/", views.community_manage, name="manage"),
    path("<slug:slug>/members/<int:user_id>/", views.member_action, name="member_action"),

    path("<slug:slug>/events/", views.event_list, name="event_list"),
    path("<slug:slug>/events/new/", views.event_create, name="event_create"),
    path("<slug:slug>/events/<int:event_id>/", views.event_detail, name="event_detail"),
    path("<slug:slug>/events/<int:event_id>/rsvp/", views.event_rsvp, name="event_rsvp"),
    path("<slug:slug>/events/<int:event_id>/delete/", views.event_delete, name="event_delete"),
]
