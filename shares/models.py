from django.db import models
from django.db.models import Sum
from decimal import Decimal
from members.models import Member


class ShareConfig(models.Model):
    """
    Singleton — one row defines the SACCO's share capital rules.
    Use ShareConfig.get() to always get the active config.
    """
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='share_configs',
        null=True, blank=True
    )
    par_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('100.00'),
        help_text='Price per share (KES)'
    )
    min_shares = models.PositiveIntegerField(
        default=1,
        help_text='Minimum shares a member must hold to remain in good standing'
    )
    max_shares = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Maximum shares any one member can hold (leave blank for no limit)'
    )
    loan_multiplier = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('3.00'),
        help_text='Max loan = share value × this multiplier (used by loan products with shares basis)'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Share Configuration'

    def __str__(self):
        return f'Share Config — KES {self.par_value}/share'

    @classmethod
    def get(cls, chama=None):
        if chama:
            obj, _ = cls.objects.get_or_create(chama=chama)
        else:
            obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ShareAccount(models.Model):
    """One share account per member."""
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='share_account')
    shares_held = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.member.name} — {self.shares_held} shares'

    @property
    def share_value(self):
        config = ShareConfig.get(chama=self.member.chama)
        return Decimal(str(self.shares_held)) * config.par_value

    @property
    def max_loan_from_shares(self):
        config = ShareConfig.get(chama=self.member.chama)
        return self.share_value * config.loan_multiplier

    def is_in_good_standing(self):
        config = ShareConfig.get(chama=self.member.chama)
        return self.shares_held >= config.min_shares


class ShareTransaction(models.Model):
    TYPE_PURCHASE = 'purchase'
    TYPE_TRANSFER_IN = 'transfer_in'
    TYPE_TRANSFER_OUT = 'transfer_out'
    TYPE_REFUND = 'refund'
    TYPE_BONUS = 'bonus'
    TYPE_ADJUSTMENT = 'adjustment'

    TYPE_CHOICES = [
        (TYPE_PURCHASE, 'Share Purchase'),
        (TYPE_TRANSFER_IN, 'Transfer In'),
        (TYPE_TRANSFER_OUT, 'Transfer Out'),
        (TYPE_REFUND, 'Share Refund (Exit)'),
        (TYPE_BONUS, 'Bonus Shares'),
        (TYPE_ADJUSTMENT, 'Manual Adjustment'),
    ]

    account = models.ForeignKey(ShareAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    shares = models.PositiveIntegerField(help_text='Number of shares in this transaction')
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text='KES value of this transaction')
    reference = models.CharField(max_length=100, blank=True, help_text='M-Pesa code, cheque no., etc.')
    payment_mode = models.CharField(max_length=20, choices=[
        ('cash',   'Cash'),
        ('mpesa',  'M-Pesa'),
        ('bank',   'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('other',  'Other'),
    ], default='cash')
    notes = models.TextField(blank=True)
    date = models.DateField()
    created_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='share_transactions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.account.member.name} | {self.get_transaction_type_display()} | {self.shares} shares'
