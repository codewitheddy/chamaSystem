"""
Double-entry accounting models.

Every financial event creates a JournalEntry with two or more JournalLines
that balance (sum of debits == sum of credits).

Account types and their normal balances:
  Asset     → increases with Debit,  decreases with Credit
  Liability → increases with Credit, decreases with Debit
  Equity    → increases with Credit, decreases with Debit
  Income    → increases with Credit, decreases with Debit
  Expense   → increases with Debit,  decreases with Credit
"""
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


class Account(models.Model):
    """Chart of Accounts entry."""
    TYPE_ASSET     = 'asset'
    TYPE_LIABILITY = 'liability'
    TYPE_EQUITY    = 'equity'
    TYPE_INCOME    = 'income'
    TYPE_EXPENSE   = 'expense'
    TYPE_CHOICES = [
        (TYPE_ASSET,     'Asset'),
        (TYPE_LIABILITY, 'Liability'),
        (TYPE_EQUITY,    'Equity'),
        (TYPE_INCOME,    'Income'),
        (TYPE_EXPENSE,   'Expense'),
    ]

    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='accounts',
        null=True, blank=True
    )
    code = models.CharField(max_length=20, help_text='e.g. 1000, 4100')
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False,
        help_text='System accounts are auto-created and cannot be deleted')
    parent = models.ForeignKey('self', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='children')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']
        unique_together = [['chama', 'code']]

    def __str__(self):
        return f"{self.code} — {self.name}"

    @property
    def normal_balance(self):
        """Debit-normal or Credit-normal."""
        return 'debit' if self.account_type in (self.TYPE_ASSET, self.TYPE_EXPENSE) else 'credit'

    def balance(self, date_from=None, date_to=None):
        """
        Returns the account balance as a signed Decimal.
        Positive = normal balance direction.
        """
        qs = self.lines.filter(entry__is_posted=True)
        if date_from:
            qs = qs.filter(entry__date__gte=date_from)
        if date_to:
            qs = qs.filter(entry__date__lte=date_to)
        debits  = qs.filter(side='debit').aggregate(t=models.Sum('amount'))['t'] or Decimal('0')
        credits = qs.filter(side='credit').aggregate(t=models.Sum('amount'))['t'] or Decimal('0')
        if self.normal_balance == 'debit':
            return debits - credits
        return credits - debits


class JournalEntry(models.Model):
    """A balanced accounting entry (sum of debits == sum of credits)."""
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='journal_entries',
        null=True, blank=True
    )
    date = models.DateField()
    reference = models.CharField(max_length=100, blank=True,
        help_text='e.g. CONT-001, LOAN-005')
    description = models.CharField(max_length=500)
    is_posted = models.BooleanField(default=True,
        help_text='Unposted entries are drafts and excluded from reports')
    is_reversed = models.BooleanField(default=False)
    reversal_of = models.OneToOneField('self', null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name='reversed_by')
    # Source link — which app event created this entry
    source_app = models.CharField(max_length=50, blank=True,
        help_text='e.g. contributions, loans, payments')
    source_id = models.PositiveIntegerField(null=True, blank=True)

    created_by = models.ForeignKey(User, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name='journal_entries')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name_plural = 'Journal Entries'

    def __str__(self):
        return f"JE-{self.pk:04d} | {self.date} | {self.description}"

    @property
    def total_debits(self):
        return self.lines.filter(side='debit').aggregate(
            t=models.Sum('amount'))['t'] or Decimal('0')

    @property
    def total_credits(self):
        return self.lines.filter(side='credit').aggregate(
            t=models.Sum('amount'))['t'] or Decimal('0')

    @property
    def is_balanced(self):
        return self.total_debits == self.total_credits


class JournalLine(models.Model):
    """A single debit or credit line within a JournalEntry."""
    DEBIT  = 'debit'
    CREDIT = 'credit'
    SIDE_CHOICES = [(DEBIT, 'Debit'), (CREDIT, 'Credit')]

    entry   = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='lines')
    side    = models.CharField(max_length=6, choices=SIDE_CHOICES)
    amount  = models.DecimalField(max_digits=14, decimal_places=2)
    memo    = models.CharField(max_length=255, blank=True)
    member  = models.ForeignKey('members.Member', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='journal_lines')

    class Meta:
        ordering = ['side', '-amount']

    def __str__(self):
        return f"{self.get_side_display()} {self.account} KES {self.amount}"
