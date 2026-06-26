from django import forms
from .models import Member


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            'name', 'phone', 'id_number', 'email', 'date_joined', 'registration_fee',
            'reg_payment_mode', 'reg_payment_reference',
            'profile_photo', 'id_front', 'id_back',
            'next_of_kin_name', 'next_of_kin_phone', 'next_of_kin_relation',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 0712345678'}),
            'id_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID or Passport number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'date_joined': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'registration_fee': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reg_payment_mode': forms.Select(attrs={'class': 'form-select'}),
            'reg_payment_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'M-Pesa code, receipt no. (optional)'}),
            'profile_photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'id_front': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'id_back': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'next_of_kin_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'next_of_kin_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone number'}),
            'next_of_kin_relation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Spouse, Parent, Sibling'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone'].required = True
        self.fields['id_number'].required = True


class MemberDeactivateForm(forms.Form):
    reason = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Resigned, Relocated, Suspended...'
        }),
        label='Reason (optional)'
    )


class MemberExitForm(forms.Form):
    SETTLEMENT_CHOICES = [
        ('cash',   'Cash'),
        ('mpesa',  'M-Pesa'),
        ('bank',   'Bank Transfer'),
        ('waived', 'Waived / Written Off'),
    ]

    settlement_amount = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00',
        }),
        label='Settlement Amount (KES)',
        help_text='Actual amount paid out to member (refund) or collected from member (debt). Leave blank if zero.'
    )
    settlement_method = forms.ChoiceField(
        required=False,
        choices=[('', '— Select method —')] + SETTLEMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Payment Method'
    )
    settlement_ref = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. M-Pesa code, cheque no., receipt no.'
        }),
        label='Reference / Transaction Code'
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for exit, any outstanding agreements...'
        }),
        label='Exit Notes'
    )
    confirm = forms.BooleanField(
        required=True,
        label='I confirm the account settlement has been reviewed and agreed upon.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
