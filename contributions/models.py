from django.db import models
from django.contrib.auth.models import User
from members.models import Member


MONTH_CHOICES = [
    (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
    (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
    (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
]

PAYMENT_MODE_CHOICES = [
    ('cash',   'Cash'),
    ('mpesa',  'M-Pesa'),
    ('bank',   'Bank Transfer'),
    ('cheque', 'Cheque'),
    ('other',  'Other'),
]


class Contribution(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    month = models.IntegerField(choices=MONTH_CHOICES)
    year = models.IntegerField(default=2024)
    payment_mode      = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, default='cash')
    payment_reference = models.CharField(max_length=100, blank=True, help_text='M-Pesa code, receipt no., etc.')
    is_voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    # Audit trail
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='contributions_created')
    voided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name='contributions_voided')
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date']
        unique_together = [['member', 'month', 'year']]

    def __str__(self):
        return f"{self.member.name} - {self.get_month_display()} {self.year}"
