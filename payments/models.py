from django.db import models
from django.contrib.auth.models import User
from members.models import Member
from loans.models import Loan


class Payment(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('cash',   'Cash'),
        ('mpesa',  'M-Pesa'),
        ('bank',   'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('other',  'Other'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    payment_mode      = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='cash')
    payment_reference = models.CharField(max_length=100, blank=True, help_text='M-Pesa code, receipt no., etc.')
    notes = models.TextField(blank=True)
    is_voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    # Audit trail
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='payments_created')
    voided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name='payments_voided')
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=['loan', 'amount', 'date'],
                name='unique_payment_per_loan_date_amount'
            )
        ]

    def __str__(self):
        return f"{self.member.name} - KES {self.amount} on {self.date}"
