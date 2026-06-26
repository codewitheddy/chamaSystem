from django.db import models
from django.contrib.auth.models import User
from members.models import Member


class AGM(models.Model):
    chama = models.ForeignKey(
        'tenants.Chama', on_delete=models.CASCADE, related_name='agms',
        null=True, blank=True
    )
    STATUS_DRAFT = 'draft'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_OPEN = 'open'        # meeting in progress, voting live
    STATUS_CLOSED = 'closed'    # meeting ended, results final
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_OPEN, 'Open / In Progress'),
        (STATUS_CLOSED, 'Closed'),
    ]

    title = models.CharField(max_length=200, help_text='e.g. 2025 Annual General Meeting')
    year = models.PositiveIntegerField()
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    venue = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    quorum = models.PositiveIntegerField(default=0,
        help_text='Minimum members required for valid meeting (0 = no quorum check)')
    notice = models.TextField(blank=True,
        help_text='Official notice / invitation text sent to members')
    minutes = models.TextField(blank=True,
        help_text='Full meeting minutes recorded during/after the AGM')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='agms_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'AGM'

    def __str__(self):
        return f"{self.title} ({self.date})"

    @property
    def attendance_count(self):
        return self.attendances.filter(present=True).count()

    @property
    def quorum_met(self):
        if self.quorum == 0:
            return True
        return self.attendance_count >= self.quorum

    @property
    def total_members(self):
        qs = Member.objects.filter(status='active')
        if self.chama_id:
            qs = qs.filter(chama_id=self.chama_id)
        return qs.count()


class AgendaItem(models.Model):
    TYPE_DISCUSSION = 'discussion'
    TYPE_RESOLUTION = 'resolution'
    TYPE_ELECTION = 'election'
    TYPE_REPORT = 'report'
    TYPE_CHOICES = [
        (TYPE_DISCUSSION, 'Discussion'),
        (TYPE_RESOLUTION, 'Resolution / Motion'),
        (TYPE_ELECTION, 'Election'),
        (TYPE_REPORT, 'Report Presentation'),
    ]

    agm = models.ForeignKey(AGM, on_delete=models.CASCADE, related_name='agenda_items')
    order = models.PositiveIntegerField(default=1)
    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_DISCUSSION)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    presenter = models.CharField(max_length=200, blank=True,
        help_text='Name of person presenting this item')
    notes = models.TextField(blank=True, help_text='Notes recorded during discussion')
    is_done = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.order}. {self.title}"


class Resolution(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_VOTING = 'voting'
    STATUS_PASSED = 'passed'
    STATUS_FAILED = 'failed'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_VOTING, 'Voting Open'),
        (STATUS_PASSED, 'Passed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_WITHDRAWN, 'Withdrawn'),
    ]

    agm = models.ForeignKey(AGM, on_delete=models.CASCADE, related_name='resolutions')
    agenda_item = models.OneToOneField(AgendaItem, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name='resolution')
    title = models.CharField(max_length=255)
    motion_text = models.TextField(help_text='The exact wording of the motion put to vote')
    proposed_by = models.ForeignKey(Member, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='resolutions_proposed')
    seconded_by = models.ForeignKey(Member, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='resolutions_seconded')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    anonymous_voting = models.BooleanField(default=False,
        help_text='If enabled, individual votes are hidden from non-admins')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['agm', 'created_at']

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"

    @property
    def votes_yes(self):
        return self.votes.filter(choice=Vote.YES).count()

    @property
    def votes_no(self):
        return self.votes.filter(choice=Vote.NO).count()

    @property
    def votes_abstain(self):
        return self.votes.filter(choice=Vote.ABSTAIN).count()

    @property
    def total_votes(self):
        return self.votes.count()

    @property
    def passed(self):
        return self.votes_yes > self.votes_no


class Vote(models.Model):
    YES = 'yes'
    NO = 'no'
    ABSTAIN = 'abstain'
    CHOICES = [(YES, 'Yes'), (NO, 'No'), (ABSTAIN, 'Abstain')]

    resolution = models.ForeignKey(Resolution, on_delete=models.CASCADE, related_name='votes')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='agm_votes')
    choice = models.CharField(max_length=10, choices=CHOICES)
    cast_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('resolution', 'member')

    def __str__(self):
        return f"{self.member.name} → {self.choice} on '{self.resolution.title}'"


class AGMAttendance(models.Model):
    agm = models.ForeignKey(AGM, on_delete=models.CASCADE, related_name='attendances')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='agm_attendances')
    present = models.BooleanField(default=False)
    represented_by = models.CharField(max_length=200, blank=True,
        help_text='Name of proxy if member is represented')
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('agm', 'member')
        ordering = ['member__name']

    def __str__(self):
        return f"{self.member.name} — {'Present' if self.present else 'Absent'}"
