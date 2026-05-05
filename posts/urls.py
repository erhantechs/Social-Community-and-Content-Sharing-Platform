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
    path("saved/", views.saved_posts, name="saved"),
    path("<int:pk>/comment/", views.comment_create, name="comment_create"),
    path("comments/<int:pk>/like/", views.toggle_comment_like, name="toggle_comment_like"),
    path("comments/<int:pk>/delete/", views.comment_delete, name="comment_delete"),

    path("stories/new/", views.story_create, name="story_create"),
]
