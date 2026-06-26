from django.db import models
from decimal import Decimal


class Transaction(models.Model):
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='transactions',
        null=True, blank=True
    )
    # Direction
    CREDIT = 'credit'   # money coming IN to the group fund
    DEBIT  = 'debit'    # money going OUT of the group fund

    DIRECTION_CHOICES = [(CREDIT, 'Credit (In)'), (DEBIT, 'Debit (Out)')]

    # Categories
    CAT_CONTRIBUTION   = 'contribution'
    CAT_REGISTRATION   = 'registration'
    CAT_LOAN_ISSUED    = 'loan_issued'
    CAT_LOAN_REPAYMENT = 'loan_repayment'
    CAT_INTEREST       = 'interest'
    CAT_PENALTY        = 'penalty'
    CAT_EXPENSE        = 'expense'
    CAT_SHARE_CAPITAL  = 'share_capital'
    CAT_OTHER          = 'other'

    CATEGORY_CHOICES = [
        (CAT_CONTRIBUTION,   'Member Contribution'),
        (CAT_REGISTRATION,   'Registration Fee'),
        (CAT_LOAN_ISSUED,    'Loan Disbursed'),
        (CAT_LOAN_REPAYMENT, 'Loan Repayment'),
        (CAT_INTEREST,       'Interest Received'),
        (CAT_PENALTY,        'Penalty Collected'),
        (CAT_EXPENSE,        'Expense'),
        (CAT_SHARE_CAPITAL,  'Share Capital'),
        (CAT_OTHER,          'Other'),
    ]

    date        = models.DateField()
    category    = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    direction   = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    amount      = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=255)
    reference   = models.CharField(max_length=100, blank=True, help_text='e.g. Loan #5, Contribution #12')
    # optional FK links for drill-down
    member      = models.ForeignKey('members.Member', null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='transactions')
    created_at  = models.DateTimeField(auto_now_add=True)
    # manual entries can be edited; auto-generated ones are locked
    is_manual   = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} | {self.get_category_display()} | {self.direction} KES {self.amount}"


class Expense(models.Model):
    """Manual expense entries — meetings, stationery, bank charges, etc."""
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='expenses',
        null=True, blank=True
    )

    # Where the money is coming from
    SOURCE_CONTRIBUTIONS = 'contributions'
    SOURCE_REGISTRATION  = 'registration'
    SOURCE_OTHER_INCOME  = 'other_income'
    SOURCE_OUTSIDE       = 'outside'
    SOURCE_CHOICES = [
        (SOURCE_CONTRIBUTIONS, 'Contributions Fund'),
        (SOURCE_REGISTRATION,  'Registration Fees'),
        (SOURCE_OTHER_INCOME,  'Other Income (Bank Interest / Dividends)'),
        (SOURCE_OUTSIDE,       'Outside Source (Donor / Not from chama funds)'),
    ]
    INTERNAL_SOURCES = {SOURCE_CONTRIBUTIONS, SOURCE_REGISTRATION, SOURCE_OTHER_INCOME}

    date        = models.DateField()
    description = models.CharField(max_length=255)
    amount      = models.DecimalField(max_digits=12, decimal_places=2)
    category    = models.CharField(max_length=100, blank=True, help_text='e.g. Meeting, Stationery, Bank')
    fund_source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default=SOURCE_CONTRIBUTIONS,
        help_text='Which fund is this expense paid from?'
    )
    receipt_no  = models.CharField(max_length=50, blank=True)
    notes       = models.TextField(blank=True)
    is_voided   = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} — {self.description} KES {self.amount}"


class OtherIncome(models.Model):
    """
    Non-member income: bank interest, dividends, grants, donations, etc.
    Credited to the group fund and included in the income pool for profit-sharing.
    """
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='other_incomes',
        null=True, blank=True
    )

    SOURCE_BANK_INTEREST = 'bank_interest'
    SOURCE_DIVIDEND      = 'dividend'
    SOURCE_GRANT         = 'grant'
    SOURCE_DONATION      = 'donation'
    SOURCE_OTHER         = 'other'
    SOURCE_CHOICES = [
        (SOURCE_BANK_INTEREST, 'Bank Interest'),
        (SOURCE_DIVIDEND,      'Dividend / Investment Return'),
        (SOURCE_GRANT,         'Grant'),
        (SOURCE_DONATION,      'Donation'),
        (SOURCE_OTHER,         'Other'),
    ]

    date        = models.DateField()
    source      = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_OTHER)
    description = models.CharField(max_length=255)
    amount      = models.DecimalField(max_digits=14, decimal_places=2)
    reference   = models.CharField(max_length=100, blank=True, help_text='Bank slip, receipt no., etc.')
    notes       = models.TextField(blank=True)
    is_voided   = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} — {self.get_source_display()} KES {self.amount}"


class YearEndPayout(models.Model):
    """
    Records a year-end dividend/payout event.
    When the group distributes profits at year end, this tracks:
    - Total amount distributed
    - Per-member breakdown
    - The cycle resets after this
    """
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='year_end_payouts',
        null=True, blank=True
    )
    year = models.PositiveIntegerField(help_text='Financial year e.g. 2025')
    payout_date = models.DateField()
    total_contributions = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_income_pool = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_distributed = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='year_end_payouts_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-payout_date']
        unique_together = [['chama', 'year']]

    def __str__(self):
        return f"{self.chama} — {self.year} Year-End Payout (KES {self.total_distributed:,.2f})"


class YearEndPayoutLine(models.Model):
    """Per-member breakdown of a year-end payout."""
    PAYMENT_CASH = 'cash'
    PAYMENT_MPESA = 'mpesa'
    PAYMENT_BANK = 'bank'
    PAYMENT_CHOICES = [
        (PAYMENT_CASH, 'Cash'),
        (PAYMENT_MPESA, 'M-Pesa'),
        (PAYMENT_BANK, 'Bank Transfer'),
    ]

    payout = models.ForeignKey(YearEndPayout, on_delete=models.CASCADE, related_name='lines')
    member = models.ForeignKey(
        'members.Member', on_delete=models.CASCADE, related_name='year_end_payout_lines'
    )
    contributions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    profit_share = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    loan_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    penalty_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    net_payout = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_MPESA)
    payment_ref = models.CharField(max_length=100, blank=True)
    is_paid = models.BooleanField(default=False)

    class Meta:
        ordering = ['member__name']
        unique_together = [['payout', 'member']]

    def __str__(self):
        return f"{self.member.name} — KES {self.net_payout:,.2f}"
