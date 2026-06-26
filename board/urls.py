from django.urls import path
from . import views

app_name = 'board'

urlpatterns = [
    path('', views.BoardView.as_view(), name='board'),
    path('post/new/', views.BoardView.as_view(), name='post_create'),
    path('post/<int:pk>/', views.PostDetailView.as_view(), name='post_detail'),
    path('post/<int:pk>/edit/', views.PostEditView.as_view(), name='post_edit'),
    path('post/<int:pk>/delete/', views.PostDeleteView.as_view(), name='post_delete'),
    path('post/<int:pk>/pin/', views.PostPinView.as_view(), name='post_pin'),
    path('post/<int:pk>/close/', views.PostCloseView.as_view(), name='post_close'),
    path('post/<int:pk>/react/', views.ToggleReactionView.as_view(), name='post_react'),
    path('comment/<int:pk>/delete/', views.CommentDeleteView.as_view(), name='comment_delete'),
    path('mark-all-read/', views.MarkAllReadView.as_view(), name='mark_all_read'),
]
