from django.db import models
from django.db.models import Sum
from decimal import Decimal
from members.models import Member


def calculate_loan_schedule(principal, duration_months, interest_method='reducing', interest_rate=None):
    """
    Calculates repayment schedule.
    - reducing: rate applied on remaining balance each month
    - fixed:    rate applied on original principal each month (flat interest)
    interest_rate: monthly rate as Decimal (e.g. Decimal('0.05') for 5%)
    If interest_rate is None, falls back to legacy tiered reducing (5%/7%).
    """
    schedule = []
    balance = Decimal(str(principal))
    monthly_principal = (balance / duration_months).quantize(Decimal('0.01'))
    total_interest = Decimal('0.00')
    fixed_interest_per_month = None

    if interest_method == 'fixed' and interest_rate is not None:
        fixed_interest_per_month = (Decimal(str(principal)) * interest_rate).quantize(Decimal('0.01'))

    for month in range(1, duration_months + 1):
        if interest_method == 'fixed' and interest_rate is not None:
            rate = interest_rate
            interest = fixed_interest_per_month
        elif interest_rate is not None:
            # reducing with explicit rate
            rate = interest_rate
            interest = (balance * rate).quantize(Decimal('0.01'))
        else:
            # legacy tiered reducing
            rate = Decimal('0.05') if month <= 2 else Decimal('0.07')
            interest = (balance * rate).quantize(Decimal('0.01'))

        if month == duration_months:
            principal_payment = balance
        else:
            principal_payment = monthly_principal

        total_payment = principal_payment + interest
        total_interest += interest
        schedule.append({
            'month': month,
            'opening_balance': balance,
            'principal': principal_payment,
            'rate': rate * 100,
            'interest': interest,
            'total_payment': total_payment,
            'closing_balance': (balance - principal_payment).quantize(Decimal('0.01')),
        })
        balance = (balance - principal_payment).quantize(Decimal('0.01'))

    return schedule, total_interest


class LoanProduct(models.Model):
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='loan_products',
        null=True, blank=True
    )
    LOAN_TYPE_CHOICES = [
        ('regular', 'Regular Loan'),
        ('emergency', 'Emergency Loan'),
        ('soft', 'Soft Loan'),
        ('monthly_interest', 'Monthly Interest Loan'),
    ]
    INTEREST_METHOD_CHOICES = [
        ('reducing', 'Reducing Balance'),
        ('fixed', 'Fixed (Flat) Interest'),
        ('monthly_interest', 'Monthly Interest (accrues until paid)'),
        ('none', 'No Interest'),
    ]
    MAX_AMOUNT_BASIS_CHOICES = [
        ('fixed', 'Fixed Amount (manual KES limit)'),
        ('contributions', "Member's Total Contributions"),
        ('shares', "Member's Share Capital × Multiplier"),
        ('none', 'No Limit'),
    ]

    name = models.CharField(max_length=100)
    loan_type = models.CharField(max_length=20, choices=LOAN_TYPE_CHOICES, default='regular')
    interest_method = models.CharField(max_length=20, choices=INTEREST_METHOD_CHOICES, default='reducing')
    interest_rate_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('5.00'),
        help_text='Monthly interest rate (%)'
    )
    max_duration_months = models.PositiveIntegerField(default=12, help_text='Maximum repayment period (months)')
    max_amount_basis = models.CharField(
        max_length=20, choices=MAX_AMOUNT_BASIS_CHOICES, default='none',
        help_text='How the maximum loan amount is determined'
    )
    max_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Used only when basis is "Fixed Amount"'
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['chama', 'name'],
                name='unique_loan_product_name_per_chama'
            )
        ]

    def __str__(self):
        return self.name

    @property
    def monthly_rate(self):
        return self.interest_rate_percent / Decimal('100')

    def get_max_for_member(self, member):
        """Returns the effective max loan amount for a given member, or None if no limit."""
        if self.max_amount_basis == 'contributions':
            return Decimal(str(member.total_contributions() or 0))
        elif self.max_amount_basis == 'shares':
            try:
                return member.share_account.max_loan_from_shares
            except Exception:
                return Decimal('0.00')
        elif self.max_amount_basis == 'fixed' and self.max_amount:
            return self.max_amount
        return None


class Loan(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('cleared', 'Cleared'),
        ('late', 'Late'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    product = models.ForeignKey(
        LoanProduct, on_delete=models.SET_NULL, null=True, blank=True,
        help_text='Loan product / settings to apply'
    )
    loan_type = models.CharField(max_length=20, default='regular')  # kept for legacy filter
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    duration_months = models.PositiveIntegerField(default=1)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_taken = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_taken']

    def save(self, *args, **kwargs):
        if self.product:
            method = self.product.interest_method
            rate = self.product.monthly_rate
            self.loan_type = self.product.loan_type
        else:
            method = 'reducing'
            rate = None

        if method == 'none' or self.loan_type == 'emergency':
            self.interest_amount = Decimal('0.00')
            self.total_payable = Decimal(str(self.loan_amount))
            if self.date_taken and not self.due_date:
                from datetime import timedelta
                self.due_date = self.date_taken + timedelta(days=7)

        elif method == 'monthly_interest':
            # Interest = rate × principal × months_elapsed (accrues monthly until paid)
            # On initial save, calculate for 1 month (the due month).
            # total_payable is recalculated dynamically via recalculate_monthly_interest().
            months = max(self.duration_months, 1)
            rate_d = rate if rate is not None else Decimal('0.10')
            self.interest_amount = (Decimal(str(self.loan_amount)) * rate_d * months).quantize(Decimal('0.01'))
            self.total_payable = Decimal(str(self.loan_amount)) + self.interest_amount
            if self.date_taken and not self.due_date:
                import calendar
                from datetime import date
                month = self.date_taken.month - 1 + months
                year = self.date_taken.year + month // 12
                month = month % 12 + 1
                day = min(self.date_taken.day, calendar.monthrange(year, month)[1])
                self.due_date = date(year, month, day)

        else:
            _, total_interest = calculate_loan_schedule(
                self.loan_amount, self.duration_months, method, rate
            )
            self.interest_amount = total_interest
            self.total_payable = Decimal(str(self.loan_amount)) + total_interest
            if self.date_taken and not self.due_date:
                import calendar
                from datetime import date
                month = self.date_taken.month - 1 + self.duration_months
                year = self.date_taken.year + month // 12
                month = month % 12 + 1
                day = min(self.date_taken.day, calendar.monthrange(year, month)[1])
                self.due_date = date(year, month, day)

        if self.amount_paid >= self.total_payable:
            self.status = 'cleared'
        else:
            from datetime import date
            if self.due_date and date.today() > self.due_date:
                self.status = 'late'
            elif self.status not in ('late',):
                self.status = 'active'
        super().save(*args, **kwargs)

    def recalculate_monthly_interest(self):
        """
        For monthly_interest loans: recompute total_payable based on how many
        months have elapsed since date_taken. Called by a management command or
        manually. Each elapsed month adds rate × principal.

        Example: KES 1,000 at 10%/month
          Month 1 due: 1,000 + 100 = 1,100
          Month 2 due: 1,000 + 200 = 1,200
          Month 3 due: 1,000 + 300 = 1,300
        """
        if not self.product or self.product.interest_method != 'monthly_interest':
            return False
        if self.status == 'cleared':
            return False

        from datetime import date
        import math
        today = date.today()
        # months elapsed since date_taken (minimum 1)
        months_elapsed = (today.year - self.date_taken.year) * 12 + (today.month - self.date_taken.month)
        months_elapsed = max(months_elapsed, 1)

        rate = self.product.monthly_rate
        new_interest = (Decimal(str(self.loan_amount)) * rate * months_elapsed).quantize(Decimal('0.01'))
        new_total = Decimal(str(self.loan_amount)) + new_interest

        if new_total != self.total_payable:
            self.interest_amount = new_interest
            self.total_payable = new_total
            # Update status
            if self.amount_paid >= self.total_payable:
                self.status = 'cleared'
            else:
                self.status = 'late' if today > self.due_date else 'active'
            Loan.objects.filter(pk=self.pk).update(
                interest_amount=self.interest_amount,
                total_payable=self.total_payable,
                status=self.status,
            )
            return True
        return False

    def months_overdue(self):
        """For monthly_interest loans: how many months past due date."""
        if not self.due_date or self.status == 'cleared':
            return 0
        from datetime import date
        today = date.today()
        if today <= self.due_date:
            return 0
        return (today.year - self.due_date.year) * 12 + (today.month - self.due_date.month)

    @property
    def balance(self):
        return max(self.total_payable - self.amount_paid, 0)

    @property
    def repayment_percent(self):
        if self.total_payable == 0:
            return 0
        return min(int((self.amount_paid / self.total_payable) * 100), 100)

    @property
    def total_guaranteed(self):
        return self.guarantors.aggregate(t=models.Sum('amount_guaranteed'))['t'] or Decimal('0.00')

    @property
    def guarantee_coverage_percent(self):
        if self.loan_amount == 0:
            return 0
        return min(int((self.total_guaranteed / self.loan_amount) * 100), 100)

    def get_schedule(self):
        if self.product:
            method = self.product.interest_method
            rate = self.product.monthly_rate
        else:
            method = 'reducing'
            rate = None
        if method == 'none' or self.loan_type == 'emergency':
            return []
        if method == 'monthly_interest':
            # Show accrual table: each row = 1 month, interest compounds on principal
            from datetime import date
            import calendar
            rate_d = rate if rate is not None else Decimal('0.10')
            principal = Decimal(str(self.loan_amount))
            today = date.today()
            months_elapsed = max(
                (today.year - self.date_taken.year) * 12 + (today.month - self.date_taken.month),
                self.duration_months
            )
            rows = []
            for m in range(1, months_elapsed + 1):
                interest_so_far = (principal * rate_d * m).quantize(Decimal('0.01'))
                total_due = principal + interest_so_far
                rows.append({
                    'month': m,
                    'opening_balance': principal,
                    'principal': principal,
                    'rate': rate_d * 100,
                    'interest': (principal * rate_d).quantize(Decimal('0.01')),
                    'interest_total': interest_so_far,
                    'total_payment': total_due,
                    'closing_balance': total_due - self.amount_paid,
                })
            return rows
        schedule, _ = calculate_loan_schedule(self.loan_amount, self.duration_months, method, rate)
        return schedule

    def has_active_loan(member):
        return Loan.objects.filter(member=member, status__in=['active', 'late']).exists()

    def __str__(self):
        return f"#{self.pk} {self.member.name} — KES {self.loan_amount}"


class LoanGuarantor(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='guarantors')
    guarantor = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name='guarantees'
    )
    amount_guaranteed = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('loan', 'guarantor')

    def __str__(self):
        return f"{self.guarantor.name} guarantees KES {self.amount_guaranteed} for Loan #{self.loan.pk}"


class Collateral(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='collaterals')
    description = models.CharField(max_length=255)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2)
    document = models.FileField(upload_to='collateral_docs/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} (KES {self.estimated_value}) — Loan #{self.loan.pk}"
