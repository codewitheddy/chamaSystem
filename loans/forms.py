from django import forms
from django.core.exceptions import ValidationError
from .models import Loan, Collateral, LoanGuarantor, LoanProduct
from members.models import Member


DURATION_CHOICES = [(i, f"{i} month{'s' if i > 1 else ''}") for i in range(1, 25)]


class LoanProductForm(forms.ModelForm):
    class Meta:
        model = LoanProduct
        fields = ['name', 'loan_type', 'interest_method', 'interest_rate_percent',
                  'max_duration_months', 'max_amount_basis', 'max_amount', 'is_active', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Regular Loan 5%'}),
            'loan_type': forms.Select(attrs={'class': 'form-select'}),
            'interest_method': forms.Select(attrs={'class': 'form-select'}),
            'interest_rate_percent': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '5.00'
            }),
            'max_duration_months': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'max_amount_basis': forms.Select(attrs={'class': 'form-select', 'id': 'id_max_amount_basis'}),
            'max_amount': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '100', 'placeholder': 'e.g. 50000'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.chama = chama

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if self.chama:
            qs = LoanProduct.objects.filter(chama=self.chama, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(f'A loan product named "{name}" already exists for this chama.')
        return name

    def clean(self):
        cleaned = super().clean()
        basis = cleaned.get('max_amount_basis')
        amount = cleaned.get('max_amount')
        if basis == 'fixed' and not amount:
            self.add_error('max_amount', 'Enter a fixed amount when basis is "Fixed Amount".')
        return cleaned


class LoanForm(forms.ModelForm):
    duration_months = forms.ChoiceField(
        choices=DURATION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_duration_months'})
    )

    class Meta:
        model = Loan
        fields = ['member', 'product', 'loan_amount', 'duration_months', 'date_taken', 'notes']
        widgets = {
            'member': forms.Select(attrs={'class': 'form-select'}),
            'product': forms.Select(attrs={'class': 'form-select', 'id': 'id_product'}),
            'loan_amount': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '100',
                'id': 'id_loan_amount', 'placeholder': '0.00'
            }),
            'date_taken': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        from members.models import Member
        qs = Member.objects.exclude(status=Member.STATUS_EXITED)
        if chama is not None:
            qs = qs.filter(chama=chama)
        self.fields['member'].queryset = qs
        product_qs = LoanProduct.objects.filter(is_active=True).exclude(loan_type='emergency')
        if chama is not None:
            product_qs = product_qs.filter(chama=chama)
        self.fields['product'].queryset = product_qs
        self.fields['product'].empty_label = '— Select loan product —'
        self.fields['product'].required = False

    def clean_duration_months(self):
        val = int(self.cleaned_data['duration_months'])
        product = self.cleaned_data.get('product')
        if product and val > product.max_duration_months:
            raise ValidationError(
                f"This product allows a maximum of {product.max_duration_months} months."
            )
        return val

    def clean(self):
        cleaned = super().clean()
        member = cleaned.get('member')
        product = cleaned.get('product')
        amount = cleaned.get('loan_amount')
        if product and amount and member:
            effective_max = product.get_max_for_member(member)
            if effective_max is not None and amount > effective_max:
                basis_label = product.get_max_amount_basis_display()
                self.add_error('loan_amount',
                    f"This product limits loans to KES {effective_max:,.2f} "
                    f"({basis_label}).")
        if member and not self.instance.pk:
            if Loan.objects.filter(member=member, status__in=['active', 'late']).exists():
                raise ValidationError(
                    f"{member.name} already has an active loan. "
                    "It must be cleared before issuing a new one."
                )
        return cleaned


class LoanGuarantorForm(forms.ModelForm):
    class Meta:
        model = LoanGuarantor
        fields = ['guarantor', 'amount_guaranteed', 'notes']
        widgets = {
            'guarantor': forms.Select(attrs={'class': 'form-select'}),
            'amount_guaranteed': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '100', 'placeholder': '0.00'
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes'}),
        }

    def __init__(self, *args, loan=None, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.loan = loan
        self.fields['notes'].required = False
        qs = Member.objects.exclude(status=Member.STATUS_EXITED)
        # Always scope to the chama first
        if chama is not None:
            qs = qs.filter(chama=chama)
        elif loan is not None and loan.member.chama_id:
            qs = qs.filter(chama_id=loan.member.chama_id)
        if loan:
            # exclude the borrower and existing guarantors from choices
            existing = loan.guarantors.values_list('guarantor_id', flat=True)
            qs = qs.exclude(pk=loan.member_id).exclude(pk__in=existing)
        self.fields['guarantor'].queryset = qs

    def clean(self):
        cleaned = super().clean()
        guarantor = cleaned.get('guarantor')
        amount = cleaned.get('amount_guaranteed')
        if self.loan and guarantor and amount:
            if guarantor == self.loan.member:
                raise ValidationError("A member cannot guarantee their own loan.")
            # check guarantor doesn't have an active/late loan themselves
            if Loan.objects.filter(member=guarantor, status__in=['active', 'late']).exists():
                raise ValidationError(
                    f"{guarantor.name} has an active loan and cannot act as guarantor."
                )
        return cleaned


class CollateralForm(forms.ModelForm):
    class Meta:
        model = Collateral
        fields = ['description', 'estimated_value', 'document']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Title Deed, Vehicle'}),
            'estimated_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '100', 'placeholder': '0.00'}),
            'document': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }



class EmergencyLoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['member', 'loan_amount', 'date_taken', 'notes']
        widgets = {
            'member': forms.Select(attrs={'class': 'form-select'}),
            'loan_amount': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '100', 'placeholder': '0.00'
            }),
            'date_taken': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, chama=None, **kwargs):
        super().__init__(*args, **kwargs)
        # find the active emergency product for max_amount validation
        self._emergency_product = LoanProduct.objects.filter(
            loan_type='emergency', is_active=True
        ).first()
        qs = Member.objects.exclude(status=Member.STATUS_EXITED)
        if chama is not None:
            qs = qs.filter(chama=chama)
        self.fields['member'].queryset = qs

    def clean_loan_amount(self):
        amount = self.cleaned_data['loan_amount']
        if self._emergency_product and self._emergency_product.max_amount:
            if amount > self._emergency_product.max_amount:
                raise ValidationError(
                    f"Emergency loans cannot exceed KES {self._emergency_product.max_amount}."
                )
        elif amount > 5000:
            raise ValidationError("Emergency loans cannot exceed KES 5,000.")
        return amount

    def clean(self):
        cleaned = super().clean()
        member = cleaned.get('member')
        if member and not self.instance.pk:
            if Loan.objects.filter(member=member, status__in=['active', 'late']).exists():
                raise ValidationError(
                    f"{member.name} already has an active loan. "
                    "It must be cleared before issuing a new one."
                )
        return cleaned
