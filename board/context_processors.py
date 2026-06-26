from .models import Post, PostRead


def board_unread(request):
    """Inject unread post count into every template context."""
    if not request.user.is_authenticated:
        return {'board_unread_count': 0}
    chama = getattr(request, 'chama', None)
    qs = Post.objects.all()
    if chama:
        qs = qs.filter(chama=chama)
    read_ids = PostRead.objects.filter(
        user=request.user
    ).values_list('post_id', flat=True)
    count = qs.exclude(id__in=read_ids).count()
    return {'board_unread_count': count}
