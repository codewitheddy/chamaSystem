from django import forms
from .models import WelfareContribution, WelfareClaim, WelfareSettings
from members.models import Member


class WelfareSettingsForm(forms.ModelForm):
    class Meta:
        model = WelfareSettings
        fields = [
            'standard_contribution',
            'rate_hospital', 'rate_funeral', 'rate_maternity',
            'rate_disability', 'rate_other',
            'is_active', 'notes',
        ]
        widgets = {
            'standard_contribution': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '50', 'min': '0'
            }),
            'rate_hospital': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '50', 'min': '0', 'placeholder': 'Leave blank to use default'
            }),
            'rate_funeral': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '50', 'min': '0', 'placeholder': 'Leave blank to use default'
            }),
            'rate_maternity': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '50', 'min': '0', 'placeholder': 'Leave blank to use default'
            }),
            'rate_disability': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '50', 'min': '0', 'placeholder': 'Leave blank to use default'
            }),
            'rate_other': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '50', 'min': '0', 'placeholder': 'Leave blank to use default'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class WelfareContributionForm(forms.ModelForm):
    class Meta:
        model = WelfareContribution
        fields = ['member', 'amount', 'date', 'payment_method', 'reference', 'claim', 'notes']
        widgets = {
            'member': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '1'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'M-Pesa code / receipt'}),
            'claim': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Member.objects.filter(status='active')
        if chama is not None:
            qs = qs.filter(chama=chama)
        self.fields['member'].queryset = qs
        self.fields['claim'].required = False
        self.fields['claim'].empty_label = '— General (not tied to a claim) —'
        self.fields['claim'].queryset = WelfareClaim.objects.filter(
            status__in=['pending', 'approved']
        ).order_by('-date_filed')
        self.fields['notes'].required = False
        self.fields['reference'].required = False


class WelfareClaimForm(forms.ModelForm):
    class Meta:
        model = WelfareClaim
        fields = ['member', 'claim_type', 'beneficiary_name', 'beneficiary_relation',
                  'description', 'amount_requested', 'document', 'notes']
        widgets = {
            'member': forms.Select(attrs={'class': 'form-select'}),
            'claim_type': forms.Select(attrs={'class': 'form-select'}),
            'beneficiary_name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Leave blank if same as member'
            }),
            'beneficiary_relation': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. Self, Spouse, Child'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': 'Brief description of the event or need'
            }),
            'amount_requested': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '1', 'min': '1'
            }),
            'document': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Member.objects.filter(status='active')
        if chama is not None:
            qs = qs.filter(chama=chama)
        self.fields['member'].queryset = qs
        self.fields['beneficiary_name'].required = False
        self.fields['beneficiary_relation'].required = False
        self.fields['document'].required = False
        self.fields['notes'].required = False


class ClaimApprovalForm(forms.Form):
    amount_approved = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )


class ClaimDisbursementForm(forms.Form):
    amount_disbursed = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1'})
    )
    disbursement_method = forms.ChoiceField(
        choices=WelfareClaim.PAYMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    disbursement_ref = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'M-Pesa code / cheque number'
        })
    )


class ClaimRejectionForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                     'placeholder': 'Reason for rejection'})
    )


class BulkWelfareContributionForm(forms.Form):
    """Raise contributions from all active members for a specific claim."""
    claim = forms.ModelChoiceField(
        queryset=WelfareClaim.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label='— Select Claim —'
    )
    amount = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1'})
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    payment_method = forms.ChoiceField(
        choices=WelfareContribution.PAYMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = WelfareClaim.objects.filter(status__in=['pending', 'approved'])
        if chama:
            qs = qs.filter(chama=chama)
        self.fields['claim'].queryset = qs
