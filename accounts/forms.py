from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Password'
    }))


class MemberPortalLoginForm(forms.Form):
    username = forms.CharField(
        label='Phone Number',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'e.g. 0712345678'
        })
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Password'
        })
    )


class UserCreateForm(UserCreationForm):
    """
    Admin creates a staff/management user for a chama.
    Username is scoped as {preferred_username}.{chama_slug} to avoid cross-chama conflicts.
    If left blank, auto-generated from display name.
    """
    role = forms.ChoiceField(
        choices=[c for c in UserProfile.ROLE_CHOICES if c[0] != 'member'],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    display_name = forms.CharField(
        label='Display Name',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Edwin Kamau'})
    )
    preferred_username = forms.CharField(
        label='Preferred Username',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. edwin (leave blank to auto-generate)',
        }),
        help_text='Letters, digits, underscores only. The chama name will be appended automatically.'
    )
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['display_name', 'preferred_username', 'email', 'password1', 'password2', 'role']

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.chama = chama
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'
        if 'username' in self.fields:
            del self.fields['username']

    def clean_preferred_username(self):
        val = self.cleaned_data.get('preferred_username', '').strip()
        if not val:
            return val
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', val):
            raise forms.ValidationError('Only letters, digits, and underscores are allowed.')
        return val.lower()

    def _make_username(self):
        preferred = self.cleaned_data.get('preferred_username', '').strip()
        display = self.cleaned_data.get('display_name', '').strip()
        chama_slug = self.chama.slug if self.chama else 'default'

        if preferred:
            base = f"{preferred}.{chama_slug}"
        else:
            import re
            slug = re.sub(r'[^a-z0-9]', '', display.lower().replace(' ', ''))
            base = f"{slug}.{chama_slug}"

        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        display_name = self.cleaned_data['display_name']
        user.username = self._make_username()
        parts = display_name.strip().split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['role']
        widgets = {'role': forms.Select(attrs={'class': 'form-select'})}
