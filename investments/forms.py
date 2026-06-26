from django import forms
from .models import Investment, InvestmentTransaction, InvestmentDocument


class InvestmentForm(forms.ModelForm):
    class Meta:
        model = Investment
        fields = ['name', 'investment_type', 'description', 'amount_invested',
                  'date_invested', 'location', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control',
                                           'placeholder': 'e.g. Kilimani Plot, Safaricom Shares'}),
            'investment_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'amount_invested': forms.NumberInput(attrs={'class': 'form-control',
                                                        'step': 'any', 'min': '1'}),
            'date_invested': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'location': forms.TextInput(attrs={'class': 'form-control',
                                               'placeholder': 'e.g. Nairobi, NSE, Equity Bank'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class InvestmentUpdateForm(forms.ModelForm):
    """Edit + update valuation + exit."""
    class Meta:
        model = Investment
        fields = ['name', 'investment_type', 'description', 'status',
                  'amount_invested', 'date_invested', 'location',
                  'current_value', 'valuation_date',
                  'exit_amount', 'exit_date', 'exit_notes', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'investment_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'amount_invested': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'date_invested': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'current_value': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'valuation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'exit_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any'}),
            'exit_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'exit_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class InvestmentTransactionForm(forms.ModelForm):
    class Meta:
        model = InvestmentTransaction
        fields = ['tx_type', 'amount', 'date', 'description', 'reference']
        widgets = {
            'tx_type': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'min': '1'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.TextInput(attrs={'class': 'form-control',
                                                  'placeholder': 'e.g. Q1 rental income'}),
            'reference': forms.TextInput(attrs={'class': 'form-control',
                                                'placeholder': 'Receipt / M-Pesa / bank ref'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['reference'].required = False


class InvestmentDocumentForm(forms.ModelForm):
    class Meta:
        model = InvestmentDocument
        fields = ['title', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control',
                                            'placeholder': 'e.g. Title Deed, Share Certificate'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
