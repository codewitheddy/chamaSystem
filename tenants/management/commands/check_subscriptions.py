"""
Management command: check subscription status and send renewal reminders.
Run daily via cron: python manage.py check_subscriptions

Actions:
- Sends a 7-day warning email/notification to chamas expiring soon
- Logs expired chamas (does NOT auto-deactivate — that's a manual admin decision)
"""
from django.core.management.base import BaseCommand
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Check subscription expiry and send renewal reminders'

    def handle(self, *args, **options):
        from tenants.models import Chama

        today = date.today()
        warning_date = today + timedelta(days=7)

        # Trial expiring in 7 days
        trial_expiring = Chama.objects.filter(
            plan=Chama.PLAN_FREE,
            trial_ends__date=warning_date,
            is_active=True,
        )
        for chama in trial_expiring:
            self._notify(chama, 'trial_expiring', days_left=7)
            self.stdout.write(f"  Trial expiring in 7d: {chama.name}")

        # Trial expiring tomorrow
        trial_tomorrow = Chama.objects.filter(
            plan=Chama.PLAN_FREE,
            trial_ends__date=today + timedelta(days=1),
            is_active=True,
        )
        for chama in trial_tomorrow:
            self._notify(chama, 'trial_expiring', days_left=1)
            self.stdout.write(f"  Trial expiring tomorrow: {chama.name}")

        # Paid subscription expiring in 7 days
        sub_expiring = Chama.objects.filter(
            plan__in=[Chama.PLAN_BASIC, Chama.PLAN_STANDARD, Chama.PLAN_ENTERPRISE],
            subscription_end__date=warning_date,
            is_active=True,
        )
        for chama in sub_expiring:
            self._notify(chama, 'subscription_expiring', days_left=7)
            self.stdout.write(f"  Subscription expiring in 7d: {chama.name}")

        # Already expired (trial or paid)
        trial_expired = Chama.objects.filter(
            plan=Chama.PLAN_FREE,
            trial_ends__lt=today,
            is_active=True,
        )
        sub_expired = Chama.objects.filter(
            plan__in=[Chama.PLAN_BASIC, Chama.PLAN_STANDARD, Chama.PLAN_ENTERPRISE],
            subscription_end__lt=today,
            is_active=True,
        )

        expired_count = trial_expired.count() + sub_expired.count()
        if expired_count:
            self.stdout.write(self.style.WARNING(
                f"\n{expired_count} chama(s) have expired subscriptions. "
                f"Review in the superadmin dashboard."
            ))
            for c in trial_expired:
                self.stdout.write(f"  [TRIAL EXPIRED] {c.name} — trial ended {c.trial_ends}")
            for c in sub_expired:
                self.stdout.write(f"  [SUB EXPIRED] {c.name} — ended {c.subscription_end}")

        self.stdout.write(self.style.SUCCESS("Subscription check complete."))

    def _notify(self, chama, event, days_left):
        """Send a renewal reminder to the chama's admin users."""
        try:
            from accounts.models import UserProfile
            from django.core.mail import send_mail
            from django.conf import settings

            admins = UserProfile.objects.filter(
                chama=chama, role='admin', user__email__isnull=False
            ).exclude(user__email='').select_related('user')

            if event == 'trial_expiring':
                subject = f"Your ChamaSystem free trial expires in {days_left} day(s)"
                message = (
                    f"Dear {chama.name} Admin,\n\n"
                    f"Your 30-day free trial expires in {days_left} day(s).\n\n"
                    f"Upgrade to Basic (KES 500/mo) or Standard (KES 999/mo) to keep access.\n\n"
                    f"Contact us: hello@chamasystem.co.ke\n\nChamaSystem"
                )
            else:
                subject = f"Your ChamaSystem subscription expires in {days_left} day(s)"
                message = (
                    f"Dear {chama.name} Admin,\n\n"
                    f"Your subscription expires in {days_left} day(s).\n\n"
                    f"Please renew to avoid service interruption.\n\n"
                    f"Contact us: hello@chamasystem.co.ke\n\nChamaSystem"
                )

            for profile in admins:
                send_mail(
                    subject, message,
                    settings.DEFAULT_FROM_EMAIL,
                    [profile.user.email],
                    fail_silently=True,
                )
        except Exception:
            pass
