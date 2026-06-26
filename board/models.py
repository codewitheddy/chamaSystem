from django.db import models
from django.contrib.auth.models import User


class Post(models.Model):
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='posts',
        null=True, blank=True
    )
    CAT_ANNOUNCEMENT = 'announcement'
    CAT_DISCUSSION = 'discussion'
    CAT_CHOICES = [
        (CAT_ANNOUNCEMENT, 'Announcement'),
        (CAT_DISCUSSION, 'Discussion'),
    ]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_posts')
    category = models.CharField(max_length=20, choices=CAT_CHOICES, default=CAT_DISCUSSION)
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_pinned = models.BooleanField(default=False,
        help_text='Pinned posts always appear at the top')
    is_closed = models.BooleanField(default=False,
        help_text='Closed posts accept no new comments')
    attachment = models.FileField(upload_to='board_attachments/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return self.title

    @property
    def comment_count(self):
        return self.comments.count()

    @property
    def reaction_count(self):
        return self.reactions.count()


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_comments')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author.username} on '{self.post.title}'"


class PostReaction(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_reactions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')

    def __str__(self):
        return f"{self.user.username} liked '{self.post.title}'"


class PostRead(models.Model):
    """Tracks which posts a user has read — for unread badge."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reads')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='board_reads')
    read_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('post', 'user')
