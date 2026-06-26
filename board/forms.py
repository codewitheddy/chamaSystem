from django import forms
from .models import Post, Comment


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['category', 'title', 'body', 'attachment', 'is_pinned', 'is_closed']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control',
                                            'placeholder': 'Post title'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 5,
                                          'placeholder': 'Write your message here...'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_pinned': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_closed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['attachment'].required = False
        # Only admins/treasurers can post announcements, pin, or close
        if user:
            profile = getattr(user, 'profile', None)
            if not profile or not profile.is_treasurer:
                self.fields['category'].choices = [
                    (Post.CAT_DISCUSSION, 'Discussion')
                ]
                self.fields.pop('is_pinned', None)
                self.fields.pop('is_closed', None)
            else:
                # For new posts (no instance pk), hide is_closed —
                # closing only makes sense on an existing post
                instance = kwargs.get('instance')
                if not instance or not instance.pk:
                    self.fields.pop('is_closed', None)


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Write a reply...',
            }),
        }
