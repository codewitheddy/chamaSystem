from django import forms
from .models import ShareTransaction, ShareConfig, ShareAccount
from decimal import Decimal


class SharePurchaseForm(forms.ModelForm):
    class Meta:
        model = ShareTransaction
        fields = ['shares', 'payment_mode', 'reference', 'date', 'notes']
        widgets = {
            'date':         forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'shares':       forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'payment_mode': forms.Select(attrs={'class': 'form-select'}),
            'reference':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'M-Pesa code, receipt no. (optional)'}),
            'notes':        forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, member=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member
        chama = member.chama if member else None
        config = ShareConfig.get(chama=chama)
        self.fields['shares'].help_text = f'KES {config.par_value} per share'

    def clean_shares(self):
        shares = self.cleaned_data['shares']
        if shares < 1:
            raise forms.ValidationError('Must purchase at least 1 share.')
        chama = self.member.chama if self.member else None
        config = ShareConfig.get(chama=chama)
        if config.max_shares and self.member:
            acct, _ = ShareAccount.objects.get_or_create(member=self.member)
            if acct.shares_held + shares > config.max_shares:
                raise forms.ValidationError(
                    f'This would exceed the maximum of {config.max_shares} shares per member.'
                )
        return shares

    def save(self, commit=True):
        instance = super().save(commit=False)
        chama = self.member.chama if self.member else None
        config = ShareConfig.get(chama=chama)
        instance.amount = Decimal(str(instance.shares)) * config.par_value
        instance.transaction_type = ShareTransaction.TYPE_PURCHASE
        if commit:
            instance.save()
        return instance


class ShareAdjustmentForm(forms.ModelForm):
    class Meta:
        model = ShareTransaction
        fields = ['transaction_type', 'shares', 'amount', 'reference', 'date', 'notes']
        widgets = {
            'date':             forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'shares':           forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'amount':           forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'min': '0'}),
            'reference':        forms.TextInput(attrs={'class': 'form-control'}),
            'notes':            forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transaction_type'].choices = ShareTransaction.TYPE_CHOICES


class ShareConfigForm(forms.ModelForm):
    class Meta:
        model = ShareConfig
        fields = ['par_value', 'min_shares', 'max_shares', 'loan_multiplier']
        widgets = {
            'par_value': forms.NumberInput(attrs={
                'class': 'form-control', 'step': 'any', 'min': '1', 'id': 'id_par_value'
            }),
            'min_shares': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'id': 'id_min_shares'
            }),
            'max_shares': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'id': 'id_max_shares',
                'placeholder': 'Leave blank for no limit'
            }),
            'loan_multiplier': forms.NumberInput(attrs={
                'class': 'form-control', 'step': 'any', 'min': '0', 'id': 'id_loan_multiplier'
            }),
        }
