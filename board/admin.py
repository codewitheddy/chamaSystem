from django.contrib import admin
from .models import Post, Comment, PostReaction


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'is_pinned', 'is_closed',
                    'comment_count', 'created_at']
    list_filter = ['category', 'is_pinned', 'is_closed']
    search_fields = ['title', 'body', 'author__username']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['post', 'author', 'created_at']
    search_fields = ['body', 'author__username']


admin.site.register(PostReaction)
