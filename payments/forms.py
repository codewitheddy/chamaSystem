from django import forms
from django.core.exceptions import ValidationError
from .models import Payment
from loans.models import Loan


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['loan', 'amount', 'date', 'payment_mode', 'payment_reference', 'notes']
        widgets = {
            'loan':              forms.Select(attrs={'class': 'form-select'}),
            'amount':            forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'date':              forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_mode':      forms.Select(attrs={'class': 'form-select'}),
            'payment_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'M-Pesa code, receipt no. (optional)'}),
            'notes':             forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, chama=None, loan_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Loan.objects.filter(
            status__in=['active', 'late']
        ).exclude(member__status='exited').select_related('member')
        if chama is not None:
            qs = qs.filter(member__chama=chama)
        self.fields['loan'].queryset = qs
        self.fields['loan'].label_from_instance = lambda obj: (
            f"{obj.member.name} — KES {obj.loan_amount} (Balance: KES {obj.balance})"
        )
        if loan_id:
            try:
                self.fields['loan'].initial = Loan.objects.get(pk=loan_id)
            except Loan.DoesNotExist:
                pass

    def clean(self):
        cleaned = super().clean()
        loan = cleaned.get('loan')
        amount = cleaned.get('amount')
        if loan and amount is not None:
            if amount <= 0:
                raise ValidationError("Payment amount must be greater than zero.")
            if amount > loan.balance:
                raise ValidationError(
                    f"KES {amount} exceeds the remaining balance of KES {loan.balance}."
                )
        return cleaned


class PaymentVoidForm(forms.Form):
    reason = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Entered in error, wrong amount'}),
        label='Reason for voiding'
    )
