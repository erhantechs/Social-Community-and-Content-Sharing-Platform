from django.urls import path

from . import views

app_name = "posts"

urlpatterns = [
    path("", views.feed_view, name="feed"),
    path("explore/", views.explore_view, name="explore"),
    path("search/", views.search_posts, name="search"),

    path("new/", views.post_create, name="create"),
    path("quick/", views.quick_post_create, name="quick_create"),
    path("<int:pk>/", views.post_detail, name="detail"),
    path("<int:pk>/edit/", views.PostUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", views.PostDeleteView.as_view(), name="delete"),

    path("<int:pk>/like/", views.toggle_like, name="toggle_like"),
    path("<int:pk>/bookmark/", views.toggle_bookmark, name="toggle_bookmark"),
    path("<int:pk>/repost/", views.post_repost, name="repost"),
    path("<int:pk>/pin/", views.toggle_pin, name="toggle_pin"),
    path("saved/", views.saved_posts, name="saved"),
    path("<int:pk>/comment/", views.comment_create, name="comment_create"),
    path("comments/<int:pk>/like/", views.toggle_comment_like, name="toggle_comment_like"),
    path("comments/<int:pk>/edit/", views.comment_edit, name="comment_edit"),
    path("comments/<int:pk>/delete/", views.comment_delete, name="comment_delete"),

    path("drafts/", views.draft_list, name="draft_list"),
    path("drafts/save/", views.draft_save, name="draft_save"),
    path("drafts/<int:pk>/delete/", views.draft_delete, name="draft_delete"),

    path("stories/new/", views.story_create, name="story_create"),

    path("tag/<slug:slug>/", views.tag_view, name="tag"),
    path("tag/<slug:slug>/follow/", views.toggle_hashtag_follow, name="tag_follow"),
    path("polls/<int:pk>/vote/", views.poll_vote, name="poll_vote"),
]
