from django.db import models
from members.models import Member


class NotificationPreference(models.Model):
    """Per-member channel opt-in preferences."""
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='notification_prefs')
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"Prefs — {self.member.name}"


class Notification(models.Model):
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='notifications',
        null=True, blank=True
    )
    CHANNEL_EMAIL = 'email'
    CHANNEL_SMS = 'sms'
    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_IN_APP = 'in_app'
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, 'Email'),
        (CHANNEL_SMS, 'SMS'),
        (CHANNEL_WHATSAPP, 'WhatsApp'),
        (CHANNEL_IN_APP, 'In-App'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    EVENT_CONTRIBUTION = 'contribution'
    EVENT_LOAN_DISBURSED = 'loan_disbursed'
    EVENT_LOAN_REPAYMENT = 'loan_repayment'
    EVENT_LOAN_OVERDUE = 'loan_overdue'
    EVENT_MEETING = 'meeting'
    EVENT_PENALTY = 'penalty'
    EVENT_BROADCAST = 'broadcast'
    EVENT_CHOICES = [
        (EVENT_CONTRIBUTION, 'Contribution Recorded'),
        (EVENT_LOAN_DISBURSED, 'Loan Disbursed'),
        (EVENT_LOAN_REPAYMENT, 'Loan Repayment'),
        (EVENT_LOAN_OVERDUE, 'Loan Overdue'),
        (EVENT_MEETING, 'Meeting Reminder'),
        (EVENT_PENALTY, 'Penalty Issued'),
        (EVENT_BROADCAST, 'Broadcast Message'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    event = models.CharField(max_length=30, choices=EVENT_CHOICES)
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_channel_display()}] {self.event} → {self.member}"
