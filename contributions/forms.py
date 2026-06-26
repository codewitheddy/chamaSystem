from django import forms
from .models import Contribution
from members.models import Member


class ContributionForm(forms.ModelForm):
    class Meta:
        model = Contribution
        fields = ['member', 'amount', 'date', 'payment_mode', 'payment_reference']
        widgets = {
            'member':            forms.Select(attrs={'class': 'form-select'}),
            'amount':            forms.NumberInput(attrs={'class': 'form-control'}),
            'date':              forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_mode':      forms.Select(attrs={'class': 'form-select'}),
            'payment_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'M-Pesa code, receipt no. (optional)'}),
        }

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Member.objects.exclude(status=Member.STATUS_EXITED)
        if chama is not None:
            qs = qs.filter(chama=chama)
        self.fields['member'].queryset = qs

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.month = instance.date.month
        instance.year = instance.date.year
        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned = super().clean()
        member = cleaned.get('member')
        date = cleaned.get('date')
        if member and date:
            month = date.month
            year = date.year
            qs = Contribution.objects.filter(member=member, month=month, year=year)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                from calendar import month_name
                raise forms.ValidationError(
                    f"{member.name} already has a contribution for {month_name[month]} {year}."
                )
        return cleaned


class ContributionVoidForm(forms.Form):
    reason = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Entered in error, duplicate entry'}),
        label='Reason for voiding'
    )
