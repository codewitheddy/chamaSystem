from django import forms
from .models import Transaction, Expense, OtherIncome


class OtherIncomeForm(forms.ModelForm):
    class Meta:
        model = OtherIncome
        fields = ['date', 'source', 'description', 'amount', 'reference', 'notes']
        widgets = {
            'date':        forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'source':      forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Equity Bank interest — April 2026'}),
            'amount':      forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'reference':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bank slip, receipt no. (optional)'}),
            'notes':       forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['date', 'description', 'amount', 'category', 'fund_source', 'receipt_no', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Meeting refreshments'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Meeting, Stationery, Bank'}),
            'fund_source': forms.Select(attrs={'class': 'form-select'}),
            'receipt_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional receipt number'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ManualTransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['date', 'category', 'direction', 'amount', 'description', 'member', 'reference']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'direction': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'member': forms.Select(attrs={'class': 'form-select'}),
            'reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional reference'}),
        }

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        from members.models import Member
        self.fields['member'].required = False
        qs = Member.objects.exclude(status=Member.STATUS_EXITED)
        if chama is not None:
            qs = qs.filter(chama=chama)
        self.fields['member'].queryset = qs
        self.instance.is_manual = True
