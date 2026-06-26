from django.db import models
from members.models import Member


class Meeting(models.Model):
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='meetings',
        null=True, blank=True
    )
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    title = models.CharField(max_length=200)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    agenda = models.TextField(blank=True, help_text='Meeting agenda / topics to discuss')
    minutes = models.TextField(blank=True, help_text='Minutes recorded during/after the meeting')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.title} — {self.date}"

    @property
    def attendance_count(self):
        return self.attendances.filter(present=True).count()

    @property
    def total_members(self):
        return Member.objects.count()

    @property
    def attendance_percent(self):
        total = self.total_members
        if total == 0:
            return 0
        return min(int((self.attendance_count / total) * 100), 100)


class Attendance(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='attendances')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='attendances')
    present = models.BooleanField(default=False)
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('meeting', 'member')
        ordering = ['member__name']

    def __str__(self):
        status = 'Present' if self.present else 'Absent'
        return f"{self.member.name} — {self.meeting.title} ({status})"


class MeetingPenalty(models.Model):
    REASON_CHOICES = [
        ('late', 'Late Arrival'),
        ('absent', 'Absent Without Notice'),
        ('misconduct', 'Misconduct'),
        ('phone', 'Phone Disruption'),
        ('other', 'Other'),
    ]

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='penalties')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='penalties')
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, default='late')
    description = models.CharField(max_length=255, blank=True, help_text='Optional extra detail')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid = models.BooleanField(default=False)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Actual amount collected')
    paid_ref = models.CharField(max_length=100, blank=True,
        help_text='M-Pesa code, receipt, or other reference')
    is_voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.member.name} — {self.get_reason_display()} (KES {self.amount})"
