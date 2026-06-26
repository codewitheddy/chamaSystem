from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


class Investment(models.Model):
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='investments',
        null=True, blank=True
    )
    TYPE_PROPERTY = 'property'
    TYPE_STOCK = 'stock'
    TYPE_BUSINESS = 'business'
    TYPE_BOND = 'bond'
    TYPE_SACCO = 'sacco'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_PROPERTY, 'Property / Real Estate'),
        (TYPE_STOCK, 'Stocks / Shares'),
        (TYPE_BUSINESS, 'Business Venture'),
        (TYPE_BOND, 'Bond / Fixed Deposit'),
        (TYPE_SACCO, 'SACCO / Co-operative'),
        (TYPE_OTHER, 'Other'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_EXITED = 'exited'
    STATUS_WRITTEN_OFF = 'written_off'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_EXITED, 'Exited / Sold'),
        (STATUS_WRITTEN_OFF, 'Written Off'),
    ]

    name = models.CharField(max_length=200)
    investment_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    # Capital committed
    amount_invested = models.DecimalField(max_digits=14, decimal_places=2,
        help_text='Total capital put into this investment')
    date_invested = models.DateField()

    # Current valuation (manually updated)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='Current estimated market value')
    valuation_date = models.DateField(null=True, blank=True)

    # Exit details
    exit_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)
    exit_notes = models.TextField(blank=True)

    location = models.CharField(max_length=255, blank=True,
        help_text='Physical address, exchange, or institution')
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='investments_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_invested']

    def __str__(self):
        return f"{self.name} ({self.get_investment_type_display()})"

    @property
    def total_returns(self):
        """Sum of all income/dividend transactions."""
        return self.transactions.filter(
            tx_type__in=[InvestmentTransaction.TYPE_INCOME, InvestmentTransaction.TYPE_DIVIDEND,
                         InvestmentTransaction.TYPE_EXIT]
        ).aggregate(t=models.Sum('amount'))['t'] or Decimal('0.00')

    @property
    def total_injections(self):
        """Sum of all capital injection transactions."""
        return self.transactions.filter(
            tx_type=InvestmentTransaction.TYPE_INJECTION
        ).aggregate(t=models.Sum('amount'))['t'] or Decimal('0.00')

    @property
    def net_gain(self):
        return self.total_returns - self.amount_invested

    @property
    def roi_percent(self):
        if self.amount_invested == 0:
            return Decimal('0.00')
        return (self.net_gain / self.amount_invested * 100).quantize(Decimal('0.01'))

    @property
    def unrealised_gain(self):
        val = self.current_value or self.amount_invested
        return val - self.amount_invested


class InvestmentTransaction(models.Model):
    TYPE_INJECTION = 'injection'   # additional capital put in
    TYPE_INCOME = 'income'         # rental income, interest, etc.
    TYPE_DIVIDEND = 'dividend'     # dividend / profit share from investment
    TYPE_EXIT = 'exit'             # proceeds from selling / exiting
    TYPE_EXPENSE = 'expense'       # costs related to the investment
    TYPE_CHOICES = [
        (TYPE_INJECTION, 'Capital Injection'),
        (TYPE_INCOME, 'Income / Returns'),
        (TYPE_DIVIDEND, 'Dividend'),
        (TYPE_EXIT, 'Exit / Sale Proceeds'),
        (TYPE_EXPENSE, 'Investment Expense'),
    ]

    investment = models.ForeignKey(Investment, on_delete=models.CASCADE,
                                   related_name='transactions')
    tx_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=100, blank=True,
        help_text='Receipt, M-Pesa code, bank ref, etc.')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='investment_transactions_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.investment.name} — {self.get_tx_type_display()} KES {self.amount} on {self.date}"


class InvestmentDocument(models.Model):
    investment = models.ForeignKey(Investment, on_delete=models.CASCADE,
                                   related_name='documents')
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='investment_docs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='investment_docs_uploaded')

    def __str__(self):
        return f"{self.title} — {self.investment.name}"
