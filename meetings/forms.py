from django import forms
from .models import Meeting, Attendance, MeetingPenalty


class MeetingForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['title', 'date', 'time', 'venue', 'status', 'agenda']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Monthly Meeting — March 2026'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'venue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Community Hall'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'agenda': forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                            'placeholder': '1. Opening\n2. Contributions\n3. Loans\n4. AOB'}),
        }


class MinutesForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['minutes']
        widgets = {
            'minutes': forms.Textarea(attrs={'class': 'form-control', 'rows': 10,
                                             'placeholder': 'Record meeting minutes here...'}),
        }


class AttendanceForm(forms.Form):
    """Bulk attendance form — one checkbox per member."""
    def __init__(self, *args, meeting=None, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.meeting = meeting
        from members.models import Member
        members = Member.objects.exclude(status=Member.STATUS_EXITED)
        if chama is not None:
            members = members.filter(chama=chama)
        # Pre-populate from existing attendance records
        existing = {}
        if meeting:
            existing = {a.member_id: a for a in meeting.attendances.all()}
        for member in members:
            att = existing.get(member.pk)
            self.fields[f'present_{member.pk}'] = forms.BooleanField(
                required=False,
                initial=att.present if att else False,
                label=member.name,
            )
            self.fields[f'notes_{member.pk}'] = forms.CharField(
                required=False,
                initial=att.notes if att else '',
                widget=forms.TextInput(attrs={
                    'class': 'form-control form-control-sm',
                    'placeholder': 'e.g. Apologies sent'
                }),
            )


class PenaltyForm(forms.ModelForm):
    class Meta:
        model = MeetingPenalty
        fields = ['member', 'reason', 'description', 'amount', 'paid']
        widgets = {
            'member': forms.Select(attrs={'class': 'form-select'}),
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional detail...'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'paid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        from members.models import Member
        qs = Member.objects.exclude(status=Member.STATUS_EXITED)
        if chama is not None:
            qs = qs.filter(chama=chama)
        self.fields['member'].queryset = qs
