"""
Super-admin panel — only accessible from the root domain (no chama context).
Allows platform admins to create/manage chamas and provision their first admin user.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.conf import settings
from django.http import HttpResponseForbidden

from .models import Chama
from .forms import ChamaForm, ChamaProvisionForm, ChamaSignupForm
from accounts.models import UserProfile


def _staff_required(view_func):
    """Decorator that requires is_staff — redirects to our own login, not admin/login/."""
    from functools import wraps
    from django.utils.decorators import method_decorator
    from django.contrib.auth.decorators import login_required

    @login_required(login_url='/accounts/login/')
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("Staff access required.")
        return view_func(request, *args, **kwargs)
    return wrapper


from django.utils.decorators import method_decorator


def staff_required(cls):
    """Class decorator to require is_staff (not staff_member_required)."""
    original_dispatch = cls.dispatch

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path(), '/accounts/login/')
        if not request.user.is_staff:
            return HttpResponseForbidden("Staff access required.")
        return original_dispatch(self, request, *args, **kwargs)

    cls.dispatch = dispatch
    return cls


# ── Public landing + signup ───────────────────────────────────────────────────

class LandingView(View):
    """Public landing page served at the root domain."""
    def get(self, request):
        # Redirect authenticated users to their appropriate destination
        if request.user.is_authenticated:
            if request.user.is_staff:
                return redirect('/superadmin/')
            profile = getattr(request.user, 'profile', None)
            if profile and profile.is_member_portal:
                return redirect('/accounts/member/portal/')
            return redirect('/dashboard/')

        features = [
            ('people', 'Member Management', 'Track active, suspended, and exited members with their full financial history.'),
            ('cash-stack', 'Contributions', 'Record monthly contributions, bulk entry for all members, and automatic defaulter tracking.'),
            ('credit-card', 'Loan Management', 'Issue loans with interest schedules, guarantors, and full repayment tracking.'),
            ('calendar-event', 'Meetings & Penalties', 'Schedule meetings, record attendance, and manage fines automatically.'),
            ('graph-up-arrow', 'Investments', 'Track property, shares, and business investments with ROI calculations.'),
            ('heart-pulse', 'Welfare Fund', 'Manage welfare claims for hospital, funeral, and maternity support.'),
            ('people-fill', 'AGM & Voting', 'Run annual general meetings with live digital voting and quorum checks.'),
            ('chat-square-dots', 'Message Board', 'Group announcements and discussions for all members.'),
            ('bell', 'Notifications', 'SMS, WhatsApp, and email alerts for contributions, loans, and meetings.'),
        ]
        steps = [
            (1, 'Register your chama', 'Enter your chama name, pick a subdomain, and create your admin account in minutes.'),
            (2, 'Add your members', 'Import via CSV or add members one by one with their phone numbers.'),
            (3, 'Start managing', 'Record contributions, issue loans, schedule meetings, and track everything in real time.'),
        ]
        return render(request, 'tenants/landing.html', {
            'chama_count': Chama.objects.filter(is_active=True).count(),
            'features': features,
            'steps': steps,
        })


class ChamaSignupView(View):
    """Self-service chama registration — creates Chama + first admin user."""
    def get(self, request):
        form = ChamaSignupForm()
        return render(request, 'tenants/signup.html', {'form': form})

    def post(self, request):
        form = ChamaSignupForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data

            # Create the chama
            chama = Chama.objects.create(
                name=d['chama_name'],
                slug=d['chama_slug'],
                contact_phone=d.get('contact_phone', ''),
                contact_email=d['admin_email'],
                is_active=True,
            )

            # Seed the chart of accounts for this chama
            from ledger.coa import seed_chart_of_accounts
            seed_chart_of_accounts(chama)

            # Create the admin user
            # Use email as username for uniqueness
            username = d['admin_email'].split('@')[0]
            # Ensure username is unique
            base = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=d['admin_email'],
                password=d['admin_password'],
                first_name=d['admin_name'].split()[0],
                last_name=' '.join(d['admin_name'].split()[1:]),
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = 'admin'
            profile.chama = chama
            profile.save()

            # Determine the redirect URL
            # Always use BASE_DOMAIN from settings — never rely on request.get_host()
            # which may return localhost behind a reverse proxy.
            base_domain = settings.BASE_DOMAIN.split(':')[0]  # strip any port
            # Use https if BASE_DOMAIN is set to a real domain (not localhost/127.0.0.1)
            is_local = base_domain in ('localhost', '127.0.0.1')
            scheme = 'http' if is_local else 'https'
            redirect_url = f"{scheme}://{chama.slug}.{base_domain}/accounts/login/"

            # Send welcome email
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject=f"Welcome to ChamaSystem — {chama.name} is ready!",
                    message=(
                        f"Dear {d['admin_name']},\n\n"
                        f"Your chama has been registered successfully.\n\n"
                        f"Chama name : {chama.name}\n"
                        f"Your login : {username}\n"
                        f"Login URL  : {redirect_url}\n\n"
                        f"You have a 30-day free trial. After that, subscribe to keep access.\n\n"
                        f"Need help? Reply to this email.\n\n"
                        f"— The ChamaSystem Team"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[d['admin_email']],
                    fail_silently=True,
                )
            except Exception:
                pass

            return render(request, 'tenants/signup_success.html', {
                'chama': chama,
                'username': username,
                'redirect_url': redirect_url,
            })

        return render(request, 'tenants/signup.html', {'form': form})


@staff_required
class SuperAdminDashboardView(View):
    def get(self, request):
        from django.db.models import Count, Sum
        from decimal import Decimal

        chamas = Chama.objects.annotate(
            member_count=Count('members', distinct=True),
        ).order_by('-created_at')

        total_chamas = chamas.count()
        active_chamas = chamas.filter(is_active=True).count()

        # Only aggregate chama-level subscription data — no member/financial details
        total_platform_revenue = Chama.objects.aggregate(
            t=Sum('total_revenue'))['t'] or Decimal('0')
        mrr = chamas.filter(
            is_active=True,
            plan__in=[Chama.PLAN_BASIC, Chama.PLAN_STANDARD, Chama.PLAN_ENTERPRISE]
        ).aggregate(t=Sum('plan_price'))['t'] or Decimal('0')
        paid_chama_count = chamas.filter(
            plan__in=[Chama.PLAN_BASIC, Chama.PLAN_STANDARD, Chama.PLAN_ENTERPRISE]
        ).count()
        free_chama_count = chamas.filter(plan=Chama.PLAN_FREE).count()

        # Per-chama stats — only member count, no financial data
        chama_stats = [
            {'chama': c, 'members': c.member_count}
            for c in chamas
        ]

        from .models import SubscriptionPaymentRequest
        pending_payments = SubscriptionPaymentRequest.objects.filter(
            status='pending'
        ).select_related('chama').order_by('-submitted_at')

        return render(request, 'tenants/dashboard.html', {
            'chamas': chamas,
            'chama_stats': chama_stats,
            'total_chamas': total_chamas,
            'active_chamas': active_chamas,
            'total_platform_revenue': total_platform_revenue,
            'mrr': mrr,
            'paid_chama_count': paid_chama_count,
            'free_chama_count': free_chama_count,
            'plan_choices': Chama.PLAN_CHOICES,
            'pending_payments': pending_payments,
        })

@staff_required
class ChamaCreateView(View):
    def get(self, request):
        form = ChamaForm()
        provision_form = ChamaProvisionForm()
        return render(request, 'tenants/chama_form.html', {
            'form': form,
            'provision_form': provision_form,
            'title': 'Create New Chama',
        })

    def post(self, request):
        form = ChamaForm(request.POST, request.FILES)
        provision_form = ChamaProvisionForm(request.POST)
        if form.is_valid() and provision_form.is_valid():
            chama = form.save()

            # Seed chart of accounts
            from ledger.coa import seed_chart_of_accounts
            seed_chart_of_accounts(chama)

            # Create the first admin user for this chama
            username = provision_form.cleaned_data['admin_username']
            password = provision_form.cleaned_data['admin_password']
            email = provision_form.cleaned_data['admin_email']

            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = 'admin'
            profile.chama = chama
            profile.save()

            messages.success(
                request,
                f"Chama '{chama.name}' created. "
                f"Admin login: {username} at {chama.slug}.yourdomain.com"
            )
            return redirect('tenants:dashboard')

        return render(request, 'tenants/chama_form.html', {
            'form': form,
            'provision_form': provision_form,
            'title': 'Create New Chama',
        })


@staff_required
class ChamaUpdateView(View):
    def get(self, request, pk):
        chama = get_object_or_404(Chama, pk=pk)
        form = ChamaForm(instance=chama)
        return render(request, 'tenants/chama_form.html', {
            'form': form,
            'chama': chama,
            'title': f'Edit — {chama.name}',
        })

    def post(self, request, pk):
        chama = get_object_or_404(Chama, pk=pk)
        form = ChamaForm(request.POST, request.FILES, instance=chama)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{chama.name}' updated.")
            return redirect('tenants:dashboard')
        return render(request, 'tenants/chama_form.html', {
            'form': form,
            'chama': chama,
            'title': f'Edit — {chama.name}',
        })


@staff_required
class ChamaToggleView(View):
    def post(self, request, pk):
        chama = get_object_or_404(Chama, pk=pk)
        chama.is_active = not chama.is_active
        chama.save()
        status = "activated" if chama.is_active else "deactivated"
        messages.success(request, f"'{chama.name}' {status}.")
        return redirect('tenants:dashboard')

@staff_required
class ChamaPlanView(View):
    """Update a chama's subscription plan and optionally record a payment."""
    def post(self, request, pk):
        chama = get_object_or_404(Chama, pk=pk)
        plan = request.POST.get('plan', '').strip()
        record_payment = request.POST.get('record_payment') == '1'
        months = int(request.POST.get('months', 1) or 1)
        custom_price = request.POST.get('custom_price', '').strip()

        valid_plans = [p[0] for p in Chama.PLAN_CHOICES]
        if plan not in valid_plans:
            messages.error(request, "Invalid plan.")
            return redirect('tenants:dashboard')

        chama.plan = plan
        if custom_price:
            from decimal import Decimal
            try:
                chama.plan_price = Decimal(custom_price)
            except Exception:
                pass
        elif plan != Chama.PLAN_ENTERPRISE:
            # Only auto-set price for non-enterprise plans
            chama.plan_price = Chama.PLAN_PRICES.get(plan, chama.plan_price)
        # For enterprise with no custom_price entered, keep existing plan_price
        chama.save()

        if record_payment and chama.plan_price > 0:
            chama.record_payment(months=months)
            messages.success(
                request,
                f"'{chama.name}' upgraded to {chama.get_plan_display()}. "
                f"KES {chama.plan_price * months:,.2f} recorded ({months} month(s))."
            )
        else:
            messages.success(request, f"'{chama.name}' plan updated to {chama.get_plan_display()}.")
        return redirect('tenants:dashboard')


# ── Chama self-service subscription ──────────────────────────────────────────

class SubscriptionView(LoginRequiredMixin, View):
    """Subscription page shown to chama admins — payment instructions + status."""
    def get(self, request):
        chama = getattr(request, 'chama', None)
        if not chama:
            return redirect('dashboard:dashboard')
        # Only admins can manage subscription
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_admin:
            return redirect('dashboard:dashboard')

        paybill = getattr(settings, 'MPESA_PAYBILL', '')
        till_number = getattr(settings, 'MPESA_TILL_NUMBER', '')
        account = f"{getattr(settings, 'MPESA_ACCOUNT_PREFIX', 'CHAMA')}-{chama.slug.upper()}"
        billing_email = getattr(settings, 'BILLING_CONTACT_EMAIL', 'billing@chamasystem.co.ke')
        billing_phone = getattr(settings, 'BILLING_CONTACT_PHONE', '')
        account_name = getattr(settings, 'MPESA_ACCOUNT_PREFIX', '')

        return render(request, 'tenants/subscription.html', {
            'chama': chama,
            'paybill': paybill,
            'till_number': till_number,
            'account': account,
            'account_name': account_name,
            'billing_email': billing_email,
            'billing_phone': billing_phone,
            'plan_choices': [
                c for c in Chama.PLAN_CHOICES if c[0] != Chama.PLAN_FREE
            ],
        })


class SubscriptionPaymentSubmitView(LoginRequiredMixin, View):
    """Chama admin submits M-Pesa reference after paying."""
    def post(self, request):
        chama = getattr(request, 'chama', None)
        if not chama:
            return redirect('dashboard:dashboard')
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_admin:
            return redirect('dashboard:dashboard')

        plan = request.POST.get('plan', '').strip()
        mpesa_ref = request.POST.get('mpesa_ref', '').strip().upper()
        months = int(request.POST.get('months', 1) or 1)

        if not mpesa_ref:
            messages.error(request, "Please enter your M-Pesa transaction code.")
            return redirect('tenants:subscription')

        valid_plans = [Chama.PLAN_BASIC, Chama.PLAN_STANDARD]
        if plan not in valid_plans:
            messages.error(request, "Invalid plan selected.")
            return redirect('tenants:subscription')

        # Save the pending payment request — superadmin will verify and activate
        from .models import SubscriptionPaymentRequest
        from decimal import Decimal
        SubscriptionPaymentRequest.objects.create(
            chama=chama,
            plan=plan,
            months=months,
            mpesa_ref=mpesa_ref,
            submitted_by=request.user,
            amount=Chama.PLAN_PRICES[plan] * months,
        )

        # Notify superadmin by email
        try:
            from django.core.mail import send_mail
            billing_email = getattr(settings, 'BILLING_CONTACT_EMAIL', '')
            if billing_email:
                send_mail(
                    f"[ChamaSystem] Payment submitted — {chama.name}",
                    f"Chama: {chama.name} ({chama.slug})\n"
                    f"Plan: {plan}\nMonths: {months}\n"
                    f"M-Pesa Ref: {mpesa_ref}\n"
                    f"Amount: KES {Chama.PLAN_PRICES[plan] * months:,.2f}\n\n"
                    f"Log in to the superadmin dashboard to verify and activate.",
                    settings.DEFAULT_FROM_EMAIL,
                    [billing_email],
                    fail_silently=True,
                )
        except Exception:
            pass

        messages.success(
            request,
            f"Payment reference {mpesa_ref} submitted. "
            f"Your subscription will be activated within 24 hours after verification."
        )
        return redirect('tenants:subscription')


@staff_required
class PaymentVerifyView(View):
    """Superadmin verifies or rejects a submitted payment."""
    def post(self, request, pk):
        from .models import SubscriptionPaymentRequest
        req = get_object_or_404(SubscriptionPaymentRequest, pk=pk, status='pending')
        action = request.POST.get('action')
        if action == 'approve':
            req.approve(reviewed_by=request.user)
            messages.success(
                request,
                f"Payment {req.mpesa_ref} verified. {req.chama.name} upgraded to {req.plan}."
            )
        elif action == 'reject':
            reason = request.POST.get('reason', 'Payment could not be verified.').strip()
            req.reject(reviewed_by=request.user, reason=reason)
            messages.warning(request, f"Payment {req.mpesa_ref} rejected.")
        return redirect('tenants:dashboard')


@staff_required
class ChamaResetPasswordView(View):
    """Superadmin resets the password for a chama's admin user."""
    def post(self, request, pk):
        chama = get_object_or_404(Chama, pk=pk)
        new_password = request.POST.get('new_password', '').strip()
        if not new_password or len(new_password) < 6:
            messages.error(request, "Password must be at least 6 characters.")
            return redirect('tenants:dashboard')

        # Find the admin user for this chama
        from accounts.models import UserProfile
        admin_profile = UserProfile.objects.filter(
            chama=chama, role='admin'
        ).select_related('user').first()

        if not admin_profile:
            messages.warning(request, f"No admin user found for {chama.name}.")
            return redirect('tenants:dashboard')

        admin_profile.user.set_password(new_password)
        admin_profile.user.save()
        messages.success(
            request,
            f"Password reset for {chama.name} admin ({admin_profile.user.username})."
        )
        return redirect('tenants:dashboard')


@staff_required
class ChamaDeleteView(View):
    """Permanently delete a chama and all its data — superadmin only."""

    def get(self, request, pk):
        """Show confirmation page with a summary of what will be deleted."""
        chama = get_object_or_404(Chama, pk=pk)
        from members.models import Member
        from contributions.models import Contribution
        from loans.models import Loan
        member_count = Member.objects.filter(chama=chama).count()
        contribution_count = Contribution.objects.filter(member__chama=chama).count()
        loan_count = Loan.objects.filter(member__chama=chama).count()
        return render(request, 'tenants/chama_confirm_delete.html', {
            'chama': chama,
            'member_count': member_count,
            'contribution_count': contribution_count,
            'loan_count': loan_count,
        })

    def post(self, request, pk):
        chama = get_object_or_404(Chama, pk=pk)
        # Require typing the chama slug to confirm
        confirm = request.POST.get('confirm_slug', '').strip()
        if confirm != chama.slug:
            messages.error(
                request,
                f"Confirmation failed. Type '{chama.slug}' exactly to delete."
            )
            return redirect('tenants:delete', pk=pk)

        name = chama.name
        # Delete all linked user profiles first so their User accounts aren't orphaned
        from accounts.models import UserProfile
        from django.contrib.auth.models import User
        user_ids = list(
            UserProfile.objects.filter(chama=chama).values_list('user_id', flat=True)
        )
        chama.delete()  # cascades members, contributions, loans, etc.
        # Delete the actual User accounts that belonged only to this chama
        User.objects.filter(pk__in=user_ids, is_staff=False).delete()

        messages.success(request, f"'{name}' and all its data have been permanently deleted.")
        return redirect('tenants:dashboard')
