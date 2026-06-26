from django import forms
from .models import AGM, AgendaItem, Resolution, Vote, AGMAttendance
from members.models import Member


class AGMForm(forms.ModelForm):
    class Meta:
        model = AGM
        fields = ['title', 'year', 'date', 'time', 'venue', 'quorum', 'notice']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control',
                                            'placeholder': 'e.g. 2025 Annual General Meeting'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': '2000'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'venue': forms.TextInput(attrs={'class': 'form-control',
                                            'placeholder': 'e.g. Community Hall, Zoom'}),
            'quorum': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'notice': forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                            'placeholder': 'Official notice text to be sent to members'}),
        }


class AGMMinutesForm(forms.ModelForm):
    class Meta:
        model = AGM
        fields = ['minutes']
        widgets = {
            'minutes': forms.Textarea(attrs={'class': 'form-control', 'rows': 12,
                                             'placeholder': 'Record full meeting minutes here...'}),
        }


class AgendaItemForm(forms.ModelForm):
    class Meta:
        model = AgendaItem
        fields = ['order', 'item_type', 'title', 'description', 'presenter']
        widgets = {
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'item_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control',
                                            'placeholder': 'e.g. Approval of 2024 Financial Statements'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'presenter': forms.TextInput(attrs={'class': 'form-control',
                                                'placeholder': 'e.g. Treasurer'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['presenter'].required = False


class ResolutionForm(forms.ModelForm):
    class Meta:
        model = Resolution
        fields = ['title', 'motion_text', 'proposed_by', 'seconded_by',
                  'anonymous_voting', 'notes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control',
                                            'placeholder': 'e.g. Increase monthly contribution'}),
            'motion_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                                 'placeholder': 'The exact wording of the motion'}),
            'proposed_by': forms.Select(attrs={'class': 'form-select'}),
            'seconded_by': forms.Select(attrs={'class': 'form-select'}),
            'anonymous_voting': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        active = Member.objects.filter(status='active')
        if chama is not None:
            active = active.filter(chama=chama)
        self.fields['proposed_by'].queryset = active
        self.fields['proposed_by'].required = False
        self.fields['proposed_by'].empty_label = '— Select member —'
        self.fields['seconded_by'].queryset = active
        self.fields['seconded_by'].required = False
        self.fields['seconded_by'].empty_label = '— Select member —'
        self.fields['notes'].required = False


class VoteForm(forms.Form):
    choice = forms.ChoiceField(
        choices=Vote.CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )


class BulkAttendanceForm(forms.Form):
    def __init__(self, *args, agm=None, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        members = Member.objects.filter(status='active').order_by('name')
        if chama is not None:
            members = members.filter(chama=chama)
        existing = {}
        if agm:
            existing = {a.member_id: a for a in agm.attendances.all()}
        for member in members:
            att = existing.get(member.pk)
            self.fields[f'present_{member.pk}'] = forms.BooleanField(
                required=False,
                initial=att.present if att else False,
                label=member.name,
            )
            self.fields[f'proxy_{member.pk}'] = forms.CharField(
                required=False,
                initial=att.represented_by if att else '',
                widget=forms.TextInput(attrs={
                    'class': 'form-control form-control-sm',
                    'placeholder': 'Proxy name (if represented)'
                }),
            )
