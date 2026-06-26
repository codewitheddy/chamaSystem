from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from members.models import Member


class WelfareSettings(models.Model):
    """Single-row config table for the welfare fund."""
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='welfare_settings',
        null=True, blank=True
    )
    standard_contribution = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('200.00'),
        help_text='Default amount each member contributes per event (used if no per-type rate is set)'
    )

    # Per-claim-type contribution rates
    rate_hospital    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Contribution per member for Hospitalisation claims')
    rate_funeral     = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Contribution per member for Funeral / Bereavement claims')
    rate_maternity   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Contribution per member for Maternity claims')
    rate_disability  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Contribution per member for Disability claims')
    rate_other       = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Contribution per member for Other claims')

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Welfare Settings'
        verbose_name_plural = 'Welfare Settings'

    def __str__(self):
        return f'Welfare Settings (KES {self.standard_contribution}/contribution)'

    def rate_for(self, claim_type):
        """Return the configured rate for a given claim type, falling back to standard."""
        mapping = {
            'hospital':   self.rate_hospital,
            'funeral':    self.rate_funeral,
            'maternity':  self.rate_maternity,
            'disability': self.rate_disability,
            'other':      self.rate_other,
        }
        return mapping.get(claim_type) or self.standard_contribution

    @classmethod
    def get(cls, chama=None):
        if chama:
            obj, _ = cls.objects.get_or_create(chama=chama)
        else:
            obj = cls.objects.first()
            if not obj:
                obj = cls.objects.create()
        return obj


class WelfareContribution(models.Model):
    """A member's payment into the welfare fund."""
    PAYMENT_CASH = 'cash'
    PAYMENT_MPESA = 'mpesa'
    PAYMENT_BANK = 'bank'
    PAYMENT_CHOICES = [
        (PAYMENT_CASH, 'Cash'),
        (PAYMENT_MPESA, 'M-Pesa'),
        (PAYMENT_BANK, 'Bank Transfer'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='welfare_contributions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default=PAYMENT_CASH)
    reference = models.CharField(max_length=100, blank=True, help_text='M-Pesa code or receipt number')
    notes = models.TextField(blank=True)
    # link to the claim this contribution was raised for (optional)
    claim = models.ForeignKey(
        'WelfareClaim', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='contributions'
    )
    is_voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='welfare_contributions_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.member.name} — KES {self.amount} on {self.date}"


class WelfareClaim(models.Model):
    """A claim against the welfare fund."""
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='welfare_claims',
        null=True, blank=True
    )
    TYPE_HOSPITAL = 'hospital'
    TYPE_FUNERAL = 'funeral'
    TYPE_MATERNITY = 'maternity'
    TYPE_DISABILITY = 'disability'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = [
        (TYPE_HOSPITAL, 'Hospitalisation'),
        (TYPE_FUNERAL, 'Funeral / Bereavement'),
        (TYPE_MATERNITY, 'Maternity'),
        (TYPE_DISABILITY, 'Disability'),
        (TYPE_OTHER, 'Other'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_DISBURSED = 'disbursed'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_DISBURSED, 'Disbursed'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='welfare_claims')
    claim_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    # beneficiary may differ from member (e.g. member's spouse)
    beneficiary_name = models.CharField(max_length=200, blank=True,
        help_text='Name of the person the claim is for (leave blank if same as member)')
    beneficiary_relation = models.CharField(max_length=100, blank=True,
        help_text='e.g. Self, Spouse, Child, Parent')
    description = models.TextField(help_text='Brief description of the event/need')
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2)
    amount_approved = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    amount_disbursed = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    date_filed = models.DateField(auto_now_add=True)
    date_approved = models.DateField(null=True, blank=True)
    date_disbursed = models.DateField(null=True, blank=True)

    # supporting document (hospital bill, death certificate, etc.)
    document = models.FileField(upload_to='welfare_docs/', null=True, blank=True)

    # workflow actors
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='welfare_claims_reviewed')
    disbursed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='welfare_claims_disbursed')
    rejection_reason = models.TextField(blank=True)

    # payment details for disbursement
    PAYMENT_CASH = 'cash'
    PAYMENT_MPESA = 'mpesa'
    PAYMENT_BANK = 'bank'
    PAYMENT_CHOICES = [
        (PAYMENT_CASH, 'Cash'),
        (PAYMENT_MPESA, 'M-Pesa'),
        (PAYMENT_BANK, 'Bank Transfer'),
    ]
    disbursement_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, blank=True)
    disbursement_ref = models.CharField(max_length=100, blank=True,
        help_text='M-Pesa code, cheque number, etc.')

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_filed', '-created_at']

    def __str__(self):
        return f"#{self.pk} {self.member.name} — {self.get_claim_type_display()} ({self.get_status_display()})"

    @property
    def beneficiary(self):
        return self.beneficiary_name or self.member.name

    @property
    def effective_amount(self):
        """Amount actually approved/disbursed, falling back to requested."""
        return self.amount_disbursed or self.amount_approved or self.amount_requested
