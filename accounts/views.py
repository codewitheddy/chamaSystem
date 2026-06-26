from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import login
from .forms import LoginForm, UserCreateForm, UserProfileForm, MemberPortalLoginForm
from .models import UserProfile
from .mixins import AdminRequiredMixin
from members.models import Member


class UserLoginView(LoginView):
    form_class = LoginForm
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if user.is_staff:
            # Always send staff to the root superadmin panel, never a chama URL
            from django.conf import settings
            base_domain = getattr(settings, 'BASE_DOMAIN', 'localhost:8000')
            scheme = 'https' if self.request.is_secure() else 'http'
            return f"{scheme}://{base_domain}/superadmin/"
        profile = getattr(user, 'profile', None)
        if profile and profile.is_member_portal:
            return reverse_lazy('accounts:member_portal')
        # Send the user to their own chama's subdomain dashboard
        if profile and profile.chama:
            from django.conf import settings
            base_domain = getattr(settings, 'BASE_DOMAIN', 'localhost:8000')
            scheme = 'https' if self.request.is_secure() else 'http'
            return f"{scheme}://{profile.chama.slug}.{base_domain}/dashboard/"
        return reverse_lazy('dashboard:dashboard')


class MemberPortalLoginView(View):
    """Separate login page for chama members (phone + password)."""
    template_name = 'accounts/member_login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            if profile and profile.is_member_portal:
                return redirect(reverse_lazy('accounts:member_portal'))
            return redirect(reverse_lazy('dashboard:dashboard'))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = MemberPortalLoginForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        from django.contrib.auth import authenticate, login as auth_login
        phone = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        # Try PhoneNumberBackend directly — bypasses AuthenticationForm's username lookup
        from accounts.backends import PhoneNumberBackend
        backend = PhoneNumberBackend()
        user = backend.authenticate(request, username=phone, password=password)

        if user is not None:
            # Ensure member portal role
            profile = getattr(user, 'profile', None)
            if not profile or not profile.is_member_portal:
                from django import forms as _forms
                form = MemberPortalLoginForm(request.POST)
                form.add_error(None, 'This account does not have member portal access.')
                return render(request, self.template_name, {'form': form})
            user.backend = 'accounts.backends.PhoneNumberBackend'
            auth_login(request, user)
            return redirect(reverse_lazy('accounts:member_portal'))

        # Authentication failed — show generic error
        form = MemberPortalLoginForm(request.POST)
        form.add_error(None, 'Incorrect phone number or password. Please try again.')
        return render(request, self.template_name, {'form': form})


class MemberPortalView(LoginRequiredMixin, View):
    """Read-only self-service statement for a logged-in member."""
    login_url = '/accounts/member/login/'
    redirect_field_name = 'next'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            if not profile:
                return redirect('accounts:logout')
            # Staff/admin who land here get redirected to dashboard
            if not profile.is_member_portal:
                return redirect('dashboard:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        profile = request.user.profile
        member = profile.member
        if not member:
            messages.error(request, "No member account linked to this login.")
            return redirect('accounts:logout')

        from loans.models import LoanGuarantor
        context = {
            'member': member,
            'contributions': member.contribution_set.filter(is_voided=False).order_by('-date'),
            'loans': member.loan_set.order_by('-date_taken'),
            'payments': member.payment_set.filter(is_voided=False).order_by('-date'),
            'penalties': member.penalties.filter(is_voided=False).order_by('-created_at'),
            'guarantees': LoanGuarantor.objects.filter(
                guarantor=member
            ).select_related('loan__member'),
            'profit_share': member.profit_share(),
        }
        return render(request, 'accounts/member_portal.html', context)


class UserLogoutView(LogoutView):
    next_page = reverse_lazy('accounts:login')


class UserListView(AdminRequiredMixin, ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        chama = getattr(self.request, 'chama', None)
        qs = User.objects.select_related('profile', 'profile__member').filter(
            is_staff=False  # exclude superusers
        )
        if chama:
            # Strictly scope to this chama — never show users from other chamas or null chamas
            qs = qs.filter(profile__chama=chama)
        else:
            # No chama context — return nothing to be safe
            qs = qs.none()
        return qs.order_by('profile__role', 'username')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # All roles available for granting — including upgrading a member
        ctx['role_choices'] = UserProfile.ROLE_CHOICES
        return ctx


class UserCreateView(AdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:users')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        role = form.cleaned_data.get('role', 'readonly')
        profile, _ = UserProfile.objects.get_or_create(user=self.object)
        profile.role = role
        profile.chama = getattr(self.request, 'chama', None)
        profile.save()
        messages.success(
            self.request,
            f"User '{self.object.get_full_name()}' created (login: {self.object.username})."
        )
        return response


class UserUpdateRoleView(AdminRequiredMixin, View):
    """Inline role update — POST only, redirects back to user list."""
    def post(self, request, pk):
        profile = get_object_or_404(UserProfile, pk=pk)
        role = request.POST.get('role', '').strip()
        valid_roles = [r[0] for r in UserProfile.ROLE_CHOICES]
        if role not in valid_roles:
            messages.error(request, "Invalid role.")
            return redirect('accounts:users')
        old_role = profile.role
        profile.role = role
        profile.save()
        # If downgrading back to member, ensure member link is intact
        if role == 'member' and not profile.member:
            messages.warning(
                request,
                f"{profile.user.username} set to Member Portal but has no linked member record. "
                "Link them from the member's profile page."
            )
        else:
            messages.success(
                request,
                f"{profile.user.username}: role changed from {old_role} to {role}."
            )
        return redirect('accounts:users')


class UserToggleActiveView(AdminRequiredMixin, View):
    """Activate or deactivate a user account."""
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user == request.user:
            messages.error(request, "You cannot deactivate your own account.")
            return redirect('accounts:users')
        user.is_active = not user.is_active
        user.save()
        action = "activated" if user.is_active else "deactivated"
        messages.success(request, f"User {user.username} {action}.")
        return redirect('accounts:users')


class UserResetPasswordView(AdminRequiredMixin, View):
    """Admin resets another user's password."""
    def get(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        return render(request, 'accounts/user_reset_password.html', {
            'target_user': target_user,
        })

    def post(self, request, pk):
        target_user = get_object_or_404(User, pk=pk)
        p1 = request.POST.get('password1', '').strip()
        p2 = request.POST.get('password2', '').strip()
        if not p1 or len(p1) < 8:
            return render(request, 'accounts/user_reset_password.html', {
                'target_user': target_user,
                'error': 'Password must be at least 8 characters.',
            })
        if p1 != p2:
            return render(request, 'accounts/user_reset_password.html', {
                'target_user': target_user,
                'error': 'Passwords do not match.',
            })
        target_user.set_password(p1)
        target_user.save()
        messages.success(request, f"Password reset for {target_user.username}.")
        return redirect('accounts:users')


class CreateMemberPortalAccountView(AdminRequiredMixin, View):
    """Create (or reset) a portal login for a specific member."""

    def post(self, request, member_id):
        member = get_object_or_404(Member, pk=member_id)
        password = request.POST.get('password', '').strip()
        if not password or len(password) < 6:
            messages.error(request, "Password must be at least 6 characters.")
            return redirect('members:detail', pk=member_id)

        phone = member.phone.strip().replace(' ', '').replace('-', '').replace('+', '')
        chama_slug = member.chama.slug if member.chama else 'default'
        target_username = f"{phone}.{chama_slug}"

        # Case 1: member already has a linked portal account → just reset the password
        try:
            existing_profile = member.portal_user  # UserProfile with member=this member
            user = existing_profile.user
            user.set_password(password)
            user.save()
            existing_profile.role = 'member'
            existing_profile.chama = member.chama
            existing_profile.save()
            messages.success(request, f"Password reset for {member.name}. Login: {user.username}")
            return redirect('members:detail', pk=member_id)
        except Exception:
            pass

        # Case 2: no existing portal account — find or create a user with the target username
        # If target username is taken by a non-member user, append member pk to avoid collision
        if User.objects.filter(username=target_username).exists():
            existing_user = User.objects.get(username=target_username)
            existing_profile = getattr(existing_user, 'profile', None)
            if existing_profile and existing_profile.role == 'member' and existing_profile.member is None:
                # Orphaned member profile — reuse it
                user = existing_user
            else:
                # Taken by someone else — use a unique fallback username
                target_username = f"{phone}.{member.pk}.{chama_slug}"
                user = User.objects.create_user(username=target_username, password='!')
        else:
            user = User.objects.create_user(username=target_username, password='!')

        user.set_password(password)
        user.first_name = member.name.split()[0]
        user.last_name = ' '.join(member.name.split()[1:])
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = 'member'
        profile.member = member
        profile.chama = member.chama
        profile.save()

        messages.success(request, f"Portal account created for {member.name}. Login: {user.username}")
        return redirect('members:detail', pk=member_id)
