from django import forms
from django.utils.text import slugify
from .models import Chama


class ChamaForm(forms.ModelForm):
    """Used by the super-admin panel."""
    class Meta:
        model = Chama
        fields = ['name', 'slug', 'tagline', 'logo', 'primary_color',
                  'is_active', 'contact_email', 'contact_phone']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control',
                                           'placeholder': 'e.g. Nairobi Women Investment Group'}),
            'slug': forms.TextInput(attrs={'class': 'form-control',
                                           'placeholder': 'e.g. nairobi-wig'}),
            'tagline': forms.TextInput(attrs={'class': 'form-control',
                                              'placeholder': 'Short description'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control',
                                                    'placeholder': 'e.g. 0712345678'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['tagline', 'logo', 'contact_email', 'contact_phone']:
            self.fields[f].required = False


class ChamaProvisionForm(forms.Form):
    """Creates the first admin user for a new chama (super-admin panel)."""
    admin_username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control',
                                      'placeholder': 'e.g. admin'})
    )
    admin_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    admin_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control',
                                          'placeholder': 'Min 8 characters'})
    )

    def clean_admin_username(self):
        from django.contrib.auth.models import User
        username = self.cleaned_data['admin_username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(f"Username '{username}' is already taken.")
        return username


class ChamaSignupForm(forms.Form):
    """
    Public self-service registration form.
    Creates a Chama + first admin user in one step.
    """
    # Chama details
    chama_name = forms.CharField(
        max_length=200,
        label='Chama Name',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Nairobi Women Investment Group',
            'autofocus': True,
        })
    )
    chama_slug = forms.SlugField(
        max_length=80,
        label='Subdomain',
        help_text='Your chama URL: {subdomain}.yourdomain.com',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. nairobi-wig',
        })
    )
    contact_phone = forms.CharField(
        max_length=20,
        required=False,
        label='Contact Phone',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 0712345678',
        })
    )

    # Admin account
    admin_name = forms.CharField(
        max_length=150,
        label='Your Full Name',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Jane Wanjiku',
        })
    )
    admin_email = forms.EmailField(
        label='Email Address',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'you@example.com',
        })
    )
    admin_password = forms.CharField(
        min_length=8,
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min 8 characters',
        })
    )
    admin_password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Repeat password',
        })
    )

    def clean_chama_name(self):
        name = self.cleaned_data['chama_name'].strip()
        if Chama.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("A chama with this name already exists.")
        return name

    def clean_chama_slug(self):
        slug = self.cleaned_data['chama_slug'].lower().strip()
        reserved = {'www', 'admin', 'superadmin', 'api', 'static', 'media', 'mail'}
        if slug in reserved:
            raise forms.ValidationError(f"'{slug}' is a reserved name. Please choose another.")
        if Chama.objects.filter(slug=slug).exists():
            raise forms.ValidationError("This subdomain is already taken.")
        return slug

    def clean_admin_email(self):
        from django.contrib.auth.models import User
        email = self.cleaned_data['admin_email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('admin_password')
        p2 = cleaned.get('admin_password2')
        if p1 and p2 and p1 != p2:
            self.add_error('admin_password2', "Passwords do not match.")
        return cleaned
