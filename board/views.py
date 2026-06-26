from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views import View

from .models import Post, Comment, PostReaction, PostRead
from .forms import PostForm, CommentForm


def _get_post(request, pk):
    chama = getattr(request, 'chama', None)
    if chama:
        return get_object_or_404(Post, pk=pk, chama=chama)
    return get_object_or_404(Post, pk=pk)


def _treasurer(user):
    p = getattr(user, 'profile', None)
    if not p or p.role not in ('admin', 'treasurer'):
        raise PermissionDenied


def _display_name(user):
    """Return a friendly display name for any user type."""
    profile = getattr(user, 'profile', None)
    if profile and profile.is_member_portal and profile.member:
        return profile.member.name
    full = user.get_full_name()
    return full if full else user.username


# ── Board home ────────────────────────────────────────────────────────────────

class BoardView(LoginRequiredMixin, View):
    def get(self, request):
        chama = getattr(request, 'chama', None)
        category = request.GET.get('cat', '')
        search_q = request.GET.get('q', '').strip()
        qs = Post.objects.select_related('author', 'author__profile', 'author__profile__member')\
                         .prefetch_related('comments', 'reactions')
        if chama:
            qs = qs.filter(chama=chama)
        if category:
            qs = qs.filter(category=category)
        if search_q:
            qs = qs.filter(Q(title__icontains=search_q) | Q(body__icontains=search_q))

        read_ids = set(PostRead.objects.filter(user=request.user).values_list('post_id', flat=True))
        unread_count = qs.exclude(id__in=read_ids).count()

        # Annotate read/unread and display name on each post
        for post in qs:
            post.author_display = _display_name(post.author)
            post.is_read = post.pk in read_ids

        paginator = Paginator(qs, 20)
        page = paginator.get_page(request.GET.get('page'))

        return render(request, 'board/board.html', {
            'page_obj': page,
            'filter_cat': category,
            'search_q': search_q,
            'unread_count': unread_count,
            'read_ids_str': '',
            'post_form': PostForm(user=request.user),
        })

    def post(self, request):
        chama = getattr(request, 'chama', None)
        form = PostForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.chama = chama
            profile = getattr(request.user, 'profile', None)
            if not profile or not profile.is_treasurer:
                post.category = Post.CAT_DISCUSSION
                post.is_pinned = False
                post.is_closed = False
            post.save()
            messages.success(request, "Post published.")
            return redirect('board:post_detail', pk=post.pk)
        qs = Post.objects.select_related('author').all()
        if chama:
            qs = qs.filter(chama=chama)
        for post in qs:
            post.author_display = _display_name(post.author)
        page = Paginator(qs, 20).get_page(1)
        return render(request, 'board/board.html', {
            'page_obj': page,
            'filter_cat': '',
            'search_q': '',
            'unread_count': 0,
            'read_ids_str': '',
            'post_form': form,
        })


# ── Post detail ───────────────────────────────────────────────────────────────

class PostDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        post = _get_post(request, pk)
        PostRead.objects.get_or_create(post=post, user=request.user)
        post.author_display = _display_name(post.author)
        liked = post.reactions.filter(user=request.user).exists()
        comments = post.comments.select_related('author', 'author__profile', 'author__profile__member').all()
        for c in comments:
            c.author_display = _display_name(c.author)
        return render(request, 'board/post_detail.html', {
            'post': post,
            'comments': comments,
            'comment_form': CommentForm(),
            'liked': liked,
        })

    def post(self, request, pk):
        post = _get_post(request, pk)
        if post.is_closed:
            messages.error(request, "This post is closed for comments.")
            return redirect('board:post_detail', pk=pk)
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            messages.success(request, "Reply posted.")
        return redirect('board:post_detail', pk=pk)


# ── Post edit / delete ────────────────────────────────────────────────────────

class PostEditView(LoginRequiredMixin, View):
    def _check_permission(self, request, post):
        profile = getattr(request.user, 'profile', None)
        if post.author != request.user and (not profile or not profile.is_admin):
            raise PermissionDenied

    def get(self, request, pk):
        post = _get_post(request, pk)
        self._check_permission(request, post)
        form = PostForm(instance=post, user=request.user)
        return render(request, 'board/post_form.html', {'form': form, 'post': post})

    def post(self, request, pk):
        post = _get_post(request, pk)
        self._check_permission(request, post)
        form = PostForm(request.POST, request.FILES, instance=post, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Post updated.")
            return redirect('board:post_detail', pk=pk)
        return render(request, 'board/post_form.html', {'form': form, 'post': post})


class PostDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        post = _get_post(request, pk)
        profile = getattr(request.user, 'profile', None)
        if post.author != request.user and (not profile or not profile.is_admin):
            raise PermissionDenied
        if post.attachment:
            post.attachment.delete(save=False)
        post.delete()
        messages.success(request, "Post deleted.")
        return redirect('board:board')


# ── Comment delete ────────────────────────────────────────────────────────────

class CommentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        profile = getattr(request.user, 'profile', None)
        if comment.author != request.user and (not profile or not profile.is_admin):
            raise PermissionDenied
        post_pk = comment.post_id
        comment.delete()
        messages.success(request, "Comment deleted.")
        return redirect('board:post_detail', pk=post_pk)


# ── Reactions (AJAX toggle) ───────────────────────────────────────────────────

class ToggleReactionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        post = _get_post(request, pk)
        reaction, created = PostReaction.objects.get_or_create(post=post, user=request.user)
        if not created:
            reaction.delete()
            liked = False
        else:
            liked = True
        return JsonResponse({'liked': liked, 'count': post.reactions.count()})


# ── Pin / close (admin/treasurer) ────────────────────────────────────────────

class PostPinView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _treasurer(request.user)
        post = _get_post(request, pk)
        post.is_pinned = not post.is_pinned
        post.save()
        return redirect('board:post_detail', pk=pk)


class PostCloseView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _treasurer(request.user)
        post = _get_post(request, pk)
        post.is_closed = not post.is_closed
        post.save()
        return redirect('board:post_detail', pk=pk)


class MarkAllReadView(LoginRequiredMixin, View):
    def get(self, request):
        chama = getattr(request, 'chama', None)
        qs = Post.objects.all()
        if chama:
            qs = qs.filter(chama=chama)
        for post in qs:
            PostRead.objects.get_or_create(post=post, user=request.user)
        messages.success(request, "All posts marked as read.")
        return redirect('board:board')
