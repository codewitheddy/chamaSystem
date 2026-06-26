from django.db import models
from django.utils.text import slugify
from decimal import Decimal


class Chama(models.Model):
    """Root tenant model. One row = one chama organisation."""

    # ── Subscription plans ────────────────────────────────────────────────────
    PLAN_FREE = 'free'
    PLAN_BASIC = 'basic'
    PLAN_STANDARD = 'standard'
    PLAN_ENTERPRISE = 'enterprise'
    PLAN_CHOICES = [
        (PLAN_FREE,       'Free Trial (30 days)'),
        (PLAN_BASIC,      'Basic — KES 500/mo'),
        (PLAN_STANDARD,   'Standard — KES 999/mo'),
        (PLAN_ENTERPRISE, 'Enterprise — Custom'),
    ]
    PLAN_PRICES = {
        PLAN_FREE:       Decimal('0.00'),
        PLAN_BASIC:      Decimal('500.00'),
        PLAN_STANDARD:   Decimal('999.00'),
        PLAN_ENTERPRISE: Decimal('0.00'),
    }

    name = models.CharField(max_length=200, unique=True,
        help_text='Full name of the chama, e.g. "Nairobi Women Investment Group"')
    slug = models.SlugField(max_length=80, unique=True,
        help_text='Subdomain identifier, e.g. "nairobi-wig" → nairobi-wig.yourdomain.com')
    tagline = models.CharField(max_length=255, blank=True,
        help_text='Short description shown on the login page')
    logo = models.ImageField(upload_to='chama_logos/', null=True, blank=True)
    primary_color = models.CharField(max_length=7, default='#2563eb',
        help_text='Hex colour for branding, e.g. #2563eb')
    is_active = models.BooleanField(default=True,
        help_text='Inactive chamas cannot log in')
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)

    # ── Subscription ──────────────────────────────────────────────────────────
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=PLAN_FREE)
    plan_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Monthly subscription amount (KES). Auto-set from plan, override for enterprise.'
    )
    trial_ends = models.DateField(null=True, blank=True,
        help_text='Date the free trial expires. Auto-set to 30 days from registration.')
    subscription_start = models.DateField(null=True, blank=True,
        help_text='Date the paid subscription started')
    subscription_end = models.DateField(null=True, blank=True,
        help_text='Date the current subscription period ends (null = active)')
    months_paid = models.PositiveIntegerField(default=0,
        help_text='Total months of paid subscription recorded')
    total_revenue = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text='Cumulative subscription revenue collected from this chama'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Chama'
        verbose_name_plural = 'Chamas'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        # Auto-set trial_ends on first save
        if not self.pk and not self.trial_ends:
            from datetime import date, timedelta
            self.trial_ends = date.today() + timedelta(days=30)
        # Auto-set plan_price from plan — but don't overwrite a manually set enterprise price
        if self.plan in self.PLAN_PRICES:
            price = self.PLAN_PRICES[self.plan]
            if price > 0:
                self.plan_price = price
            elif self.plan == self.PLAN_FREE:
                self.plan_price = Decimal('0.00')
            # Enterprise (price=0 in PLAN_PRICES): leave plan_price as-is (manually set)
        super().save(*args, **kwargs)

    @property
    def is_on_trial(self):
        from datetime import date
        return self.plan == self.PLAN_FREE and self.trial_ends and self.trial_ends >= date.today()

    @property
    def trial_days_left(self):
        from datetime import date
        if not self.trial_ends:
            return 0
        delta = (self.trial_ends - date.today()).days
        return max(delta, 0)

    @property
    def trial_expired(self):
        from datetime import date
        return self.plan == self.PLAN_FREE and self.trial_ends and self.trial_ends < date.today()

    @property
    def subscription_active(self):
        """True if the chama has valid access (trial or paid and not expired)."""
        from datetime import date
        today = date.today()
        if self.plan == self.PLAN_FREE:
            return bool(self.trial_ends and self.trial_ends >= today)
        # Paid plan — check subscription_end if set
        if self.subscription_end:
            return self.subscription_end >= today
        # Paid plan with no end date = active (manual management)
        return self.plan in (self.PLAN_BASIC, self.PLAN_STANDARD, self.PLAN_ENTERPRISE)

    @property
    def subscription_status(self):
        """Returns: 'trial', 'active', 'expired', 'trial_expired'"""
        from datetime import date
        today = date.today()
        if self.plan == self.PLAN_FREE:
            if self.trial_ends and self.trial_ends >= today:
                return 'trial'
            return 'trial_expired'
        if self.subscription_end and self.subscription_end < today:
            return 'expired'
        return 'active'

    def record_payment(self, months=1):
        """Record a subscription payment and extend the subscription period."""
        from datetime import date, timedelta
        import calendar
        today = date.today()
        self.months_paid += months
        self.total_revenue += self.plan_price * months
        if not self.subscription_start:
            self.subscription_start = today
        # Extend subscription_end by the paid months
        base = self.subscription_end if (self.subscription_end and self.subscription_end > today) else today
        month = base.month - 1 + months
        year = base.year + month // 12
        month = month % 12 + 1
        day = min(base.day, calendar.monthrange(year, month)[1])
        self.subscription_end = date(year, month, day)
        self.save(update_fields=['months_paid', 'total_revenue', 'subscription_start', 'subscription_end'])


class SubscriptionPaymentRequest(models.Model):
    """A payment submitted by a chama admin — pending superadmin verification."""
    STATUS_PENDING = 'pending'
    STATUS_VERIFIED = 'verified'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING,  'Pending Verification'),
        (STATUS_VERIFIED, 'Verified & Activated'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    chama = models.ForeignKey(Chama, on_delete=models.CASCADE, related_name='payment_requests')
    plan = models.CharField(max_length=20)
    months = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mpesa_ref = models.CharField(max_length=50, help_text='M-Pesa transaction code')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    submitted_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='subscription_requests'
    )
    reviewed_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='subscription_reviews'
    )
    rejection_reason = models.CharField(max_length=255, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.chama.name} — {self.plan} x{self.months} — {self.mpesa_ref} [{self.status}]"

    def approve(self, reviewed_by):
        """Verify payment and activate the subscription."""
        from django.utils import timezone
        self.status = self.STATUS_VERIFIED
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save()
        # Upgrade the chama plan and extend subscription
        self.chama.plan = self.plan
        self.chama.save()
        self.chama.record_payment(months=self.months)

    def reject(self, reviewed_by, reason=''):
        from django.utils import timezone
        self.status = self.STATUS_REJECTED
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.rejection_reason = reason
        self.save()
