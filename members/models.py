from django.db import models
from decimal import Decimal
from datetime import date


class Member(models.Model):
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='members',
        null=True, blank=True  # null during migration; required after
    )
    STATUS_ACTIVE = 'active'
    STATUS_DISABLED = 'disabled'
    STATUS_EXITED = 'exited'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DISABLED, 'Disabled'),
        (STATUS_EXITED, 'Exited'),
    ]

    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)  # unique per chama enforced via constraint below
    id_number = models.CharField(max_length=30, blank=True, help_text='National ID or Passport number')
    email = models.EmailField(blank=True)
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_joined = models.DateField(default=date.today)

    REG_PAYMENT_CHOICES = [
        ('cash',   'Cash'),
        ('mpesa',  'M-Pesa'),
        ('bank',   'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('other',  'Other'),
    ]
    reg_payment_mode      = models.CharField(max_length=20, choices=REG_PAYMENT_CHOICES, default='cash', blank=True)
    reg_payment_reference = models.CharField(max_length=100, blank=True, help_text='M-Pesa code, receipt no., etc.')
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    deactivation_reason = models.CharField(max_length=255, blank=True)
    exit_date = models.DateField(null=True, blank=True)
    exit_notes = models.TextField(blank=True)

    SETTLEMENT_CASH = 'cash'
    SETTLEMENT_MPESA = 'mpesa'
    SETTLEMENT_BANK = 'bank'
    SETTLEMENT_WAIVED = 'waived'
    SETTLEMENT_CHOICES = [
        (SETTLEMENT_CASH,   'Cash'),
        (SETTLEMENT_MPESA,  'M-Pesa'),
        (SETTLEMENT_BANK,   'Bank Transfer'),
        (SETTLEMENT_WAIVED, 'Waived / Written Off'),
    ]
    exit_settlement_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Actual amount paid out (refund) or collected (debt) at exit')
    exit_settlement_method = models.CharField(max_length=20, choices=SETTLEMENT_CHOICES, blank=True)
    exit_settlement_ref    = models.CharField(max_length=100, blank=True,
        help_text='M-Pesa code, cheque number, or other reference')

    # KYC / Identity documents
    profile_photo  = models.ImageField(upload_to='member_photos/', null=True, blank=True)
    id_front       = models.ImageField(upload_to='member_ids/', null=True, blank=True)
    id_back        = models.ImageField(upload_to='member_ids/', null=True, blank=True)

    # Next of kin / beneficiary
    next_of_kin_name     = models.CharField(max_length=200, blank=True)
    next_of_kin_phone    = models.CharField(max_length=20, blank=True)
    next_of_kin_relation = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['chama', 'phone'],
                name='unique_phone_per_chama'
            )
        ]

    def __str__(self):
        return self.name

    def total_contributions(self):
        return self.contribution_set.filter(is_voided=False).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

    def total_loans(self):
        return self.loan_set.aggregate(
            total=models.Sum('loan_amount')
        )['total'] or Decimal('0.00')

    def total_loan_balance(self):
        return sum(l.balance for l in self.loan_set.all())

    def unpaid_penalties(self):
        return self.penalties.filter(paid=False, is_voided=False).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

    def active_guarantees(self):
        """Loans this member is guaranteeing that are still active/late."""
        from loans.models import LoanGuarantor
        return LoanGuarantor.objects.filter(
            guarantor=self,
            loan__status__in=['active', 'late']
        ).select_related('loan__member')

    def profit_share(self):
        """
        Calculate this member's proportional share of group income.

        Income pool = interest earned + penalties collected + other credits
                      minus expenses (net profit the group has made).
        Member's share = (member contributions / total all-member contributions) × income pool.
        """
        from accounting.models import Transaction
        from django.db.models import Sum as _Sum

        # Total contributions across ALL members (the denominator) — exclude voided
        from contributions.models import Contribution
        contrib_qs = Contribution.objects.filter(is_voided=False)
        if self.chama_id:
            contrib_qs = contrib_qs.filter(member__chama=self.chama)
        total_all_contributions = contrib_qs.aggregate(t=_Sum('amount'))['t'] or Decimal('0.00')

        if total_all_contributions == 0:
            return {
                'income_pool': Decimal('0.00'),
                'member_share_pct': Decimal('0.00'),
                'member_profit': Decimal('0.00'),
            }

        # Income pool: credits that are "profit" (not capital)
        income_categories = [
            Transaction.CAT_INTEREST,
            Transaction.CAT_PENALTY,
            Transaction.CAT_REGISTRATION,
            Transaction.CAT_OTHER,
        ]
        tx_qs = Transaction.objects.all()
        if self.chama_id:
            tx_qs = tx_qs.filter(chama=self.chama)

        gross_income = tx_qs.filter(
            category__in=income_categories,
            direction=Transaction.CREDIT,
        ).aggregate(t=_Sum('amount'))['t'] or Decimal('0.00')

        # Add other income (bank interest, dividends, grants, etc.)
        from accounting.models import OtherIncome
        other_income_qs = OtherIncome.objects.filter(is_voided=False)
        if self.chama_id:
            other_income_qs = other_income_qs.filter(chama=self.chama)
        other_income = other_income_qs.aggregate(t=_Sum('amount'))['t'] or Decimal('0.00')
        gross_income += other_income

        total_expenses = tx_qs.filter(
            category=Transaction.CAT_EXPENSE,
            direction=Transaction.DEBIT,
        ).aggregate(t=_Sum('amount'))['t'] or Decimal('0.00')

        income_pool = gross_income - total_expenses
        if income_pool < 0:
            income_pool = Decimal('0.00')

        member_contributions = Decimal(str(self.total_contributions()))
        share_pct = (member_contributions / total_all_contributions * 100).quantize(Decimal('0.01'))
        member_profit = (member_contributions / total_all_contributions * income_pool).quantize(Decimal('0.01'))

        return {
            'income_pool': income_pool,
            'gross_income': gross_income,
            'total_expenses': total_expenses,
            'member_share_pct': share_pct,
            'member_profit': member_profit,
        }

    def exit_summary(self):
        """Returns a dict with all figures needed for account closure."""
        contributions = Decimal(str(self.total_contributions()))
        loan_balance  = Decimal(str(self.total_loan_balance()))
        penalties     = Decimal(str(self.unpaid_penalties()))
        reg_fee       = Decimal(str(self.registration_fee))

        ps = self.profit_share()
        member_profit = ps['member_profit']

        # Net: contributions + profit share − loan balance − unpaid penalties
        net = contributions + member_profit - loan_balance - penalties
        return {
            'contributions': contributions,
            'loan_balance': loan_balance,
            'penalties': penalties,
            'reg_fee': reg_fee,
            'income_pool': ps['income_pool'],
            'gross_income': ps['gross_income'],
            'total_expenses': ps['total_expenses'],
            'member_share_pct': ps['member_share_pct'],
            'member_profit': member_profit,
            'net': net,
            'refund_due': max(net, Decimal('0.00')),
            'amount_owed': max(-net, Decimal('0.00')),
            'active_guarantees': self.active_guarantees(),
            'has_active_loans': self.loan_set.filter(status__in=['active', 'late']).exists(),
            'has_unpaid_penalties': penalties > 0,
            'has_active_guarantees': self.active_guarantees().exists(),
        }
