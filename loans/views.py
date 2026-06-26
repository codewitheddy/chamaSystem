from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.views import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from decimal import Decimal
from .models import Loan, Collateral, LoanGuarantor, LoanProduct, calculate_loan_schedule
from .forms import LoanForm, CollateralForm, LoanGuarantorForm, EmergencyLoanForm, LoanProductForm
from accounts.mixins import TreasurerRequiredMixin, AdminRequiredMixin
from tenants.scoping import scope, scope_members


class LoanListView(LoginRequiredMixin, ListView):
    model = Loan
    template_name = 'loans/loan_list.html'
    context_object_name = 'loans'
    paginate_by = 20

    def get_queryset(self):
        qs = scope(self.request, Loan.objects.select_related('member'))
        status = self.request.GET.get('status')
        q = self.request.GET.get('q', '').strip()
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(member__name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = scope(self.request, Loan.objects.all())
        ctx['total_loans'] = base.aggregate(t=Sum('loan_amount'))['t'] or 0
        ctx['total_interest'] = base.aggregate(t=Sum('interest_amount'))['t'] or 0
        ctx['active_count'] = base.filter(status='active').count()
        ctx['cleared_count'] = base.filter(status='cleared').count()
        ctx['late_count'] = base.filter(status='late').count()
        ctx['total_balance'] = sum(l.balance for l in base)
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class LoanCreateView(TreasurerRequiredMixin, SuccessMessageMixin, CreateView):
    model = Loan
    form_class = LoanForm
    template_name = 'loans/loan_form.html'
    success_url = reverse_lazy('loans:list')
    success_message = "Loan issued successfully."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from members.models import Member
        from accounting.views import get_fund_balance
        ctx['all_members'] = scope_members(self.request)
        ctx['fund'] = get_fund_balance(self.request)
        return ctx

    def form_valid(self, form):
        from members.models import Member
        from accounting.views import get_fund_balance
        from decimal import Decimal
        member = form.cleaned_data.get('member')
        if member and member.status == Member.STATUS_EXITED:
            form.add_error('member', 'Cannot issue a loan to an exited member.')
            return self.form_invalid(form)
        # Fund availability check
        loan_amount = form.cleaned_data.get('loan_amount', Decimal('0'))
        fund = get_fund_balance(self.request)
        if loan_amount > fund['available_for_new_loans']:
            form.add_error(
                'loan_amount',
                f"Insufficient funds. Available for loans: KES {fund['available_for_new_loans']:,.2f}. "
                f"Requested: KES {loan_amount:,.2f}."
            )
            return self.form_invalid(form)
        response = super().form_valid(form)
        loan = self.object
        chama = getattr(self.request, 'chama', None)
        guarantor_ids = self.request.POST.getlist('guarantor_ids[]')
        guarantor_amounts = self.request.POST.getlist('guarantor_amounts[]')
        for gid, amt in zip(guarantor_ids, guarantor_amounts):
            try:
                from members.models import Member
                qs = Member.objects.filter(pk=gid)
                if chama:
                    qs = qs.filter(chama=chama)
                g = qs.get()
                if g != loan.member and float(amt) > 0:
                    LoanGuarantor.objects.get_or_create(
                        loan=loan, guarantor=g,
                        defaults={'amount_guaranteed': amt}
                    )
            except Exception:
                pass
        return response


class LoanUpdateView(TreasurerRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Loan
    form_class = LoanForm
    template_name = 'loans/loan_form.html'
    success_url = reverse_lazy('loans:list')
    success_message = "Loan updated."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs

    def dispatch(self, request, *args, **kwargs):
        loan = get_object_or_404(Loan, pk=kwargs['pk'])
        if loan.member.status == 'exited':
            from django.contrib import messages
            messages.error(request, "Cannot edit a loan belonging to an exited member.")
            return redirect('loans:detail', pk=loan.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('loans:detail', kwargs={'pk': self.object.pk})


class LoanDeleteView(AdminRequiredMixin, DeleteView):
    model = Loan
    template_name = 'loans/loan_confirm_delete.html'
    success_url = reverse_lazy('loans:list')

    def get_queryset(self):
        return scope(self.request, Loan.objects.all())


class LoanDetailView(LoginRequiredMixin, DetailView):
    model = Loan
    template_name = 'loans/loan_detail.html'
    context_object_name = 'loan'

    def get_queryset(self):
        return scope(self.request, Loan.objects.all())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['payments'] = self.object.payment_set.select_related('member').all()
        ctx['schedule'] = self.object.get_schedule()
        return ctx


class LoanCalculatorView(LoginRequiredMixin, View):
    """AJAX endpoint — returns interest preview for the loan form."""
    def get(self, request):
        try:
            amount = Decimal(request.GET.get('amount', '0'))
            months = int(request.GET.get('months', '1'))
            product_id = request.GET.get('product_id', '')
            if amount <= 0 or months <= 0:
                raise ValueError

            method = 'reducing'
            rate = None
            if product_id:
                try:
                    product = LoanProduct.objects.get(pk=product_id)
                    method = product.interest_method
                    rate = product.monthly_rate if method != 'none' else None
                except LoanProduct.DoesNotExist:
                    pass

            if method == 'none':
                return JsonResponse({
                    'total_interest': '0.00',
                    'total_payable': str(amount),
                    'schedule': [],
                })

            if method == 'monthly_interest':
                rate_d = rate if rate is not None else Decimal('0.10')
                rows = []
                for m in range(1, months + 1):
                    interest_this_month = (amount * rate_d).quantize(Decimal('0.01'))
                    interest_total = (amount * rate_d * m).quantize(Decimal('0.01'))
                    total_due = amount + interest_total
                    rows.append({
                        'month': m,
                        'opening_balance': str(amount),
                        'principal': str(amount),
                        'rate': str(rate_d * 100),
                        'interest': str(interest_this_month),
                        'total_payment': str(total_due),
                        'closing_balance': str(total_due),
                    })
                total_interest = amount * rate_d * months
                return JsonResponse({
                    'total_interest': str(total_interest.quantize(Decimal('0.01'))),
                    'total_payable': str((amount + total_interest).quantize(Decimal('0.01'))),
                    'schedule': rows,
                    'method': 'monthly_interest',
                    'note': f'Interest of {rate_d*100:.0f}% per month accrues on KES {amount:,.2f} until fully paid.',
                })

            schedule, total_interest = calculate_loan_schedule(amount, months, method, rate)
            total_payable = amount + total_interest
            rows = [{
                'month': r['month'],
                'opening_balance': str(r['opening_balance']),
                'principal': str(r['principal']),
                'rate': str(r['rate']),
                'interest': str(r['interest']),
                'total_payment': str(r['total_payment']),
                'closing_balance': str(r['closing_balance']),
            } for r in schedule]
            return JsonResponse({
                'total_interest': str(total_interest),
                'total_payable': str(total_payable),
                'schedule': rows,
            })
        except Exception:
            return JsonResponse({'error': 'Invalid input'}, status=400)


class LoanProductAjaxView(LoginRequiredMixin, View):
    """Returns product details for the loan form JS."""
    def get(self, request):
        product_id = request.GET.get('product_id')
        try:
            p = scope(request, LoanProduct.objects.filter(is_active=True)).get(pk=product_id)
            return JsonResponse({
                'loan_type': p.loan_type,
                'interest_method': p.interest_method,
                'interest_rate_percent': str(p.interest_rate_percent),
                'max_duration_months': p.max_duration_months,
                'max_amount_basis': p.max_amount_basis,
                'max_amount': str(p.max_amount) if p.max_amount else None,
                'is_monthly_interest': p.interest_method == 'monthly_interest',
            })
        except LoanProduct.DoesNotExist:
            return JsonResponse({}, status=404)


class LoanProductListView(AdminRequiredMixin, ListView):
    model = LoanProduct
    template_name = 'loans/loan_product_list.html'
    context_object_name = 'products'

    def get_queryset(self):
        return scope(self.request, LoanProduct.objects.all())


class LoanProductCreateView(AdminRequiredMixin, SuccessMessageMixin, CreateView):
    model = LoanProduct
    form_class = LoanProductForm
    template_name = 'loans/loan_product_form.html'
    success_url = reverse_lazy('loans:product_list')
    success_message = "Loan product created."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs

    def form_valid(self, form):
        form.instance.chama = getattr(self.request, 'chama', None)
        return super().form_valid(form)


class LoanProductUpdateView(AdminRequiredMixin, SuccessMessageMixin, UpdateView):
    model = LoanProduct
    form_class = LoanProductForm
    template_name = 'loans/loan_product_form.html'
    success_url = reverse_lazy('loans:product_list')
    success_message = "Loan product updated."

    def get_queryset(self):
        return scope(self.request, LoanProduct.objects.all())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs


class LoanProductDeleteView(AdminRequiredMixin, DeleteView):
    model = LoanProduct
    template_name = 'loans/loan_product_confirm_delete.html'
    success_url = reverse_lazy('loans:product_list')

    def get_queryset(self):
        return scope(self.request, LoanProduct.objects.all())


class MemberContributionCheckView(LoginRequiredMixin, View):
    """AJAX — returns member's total contributions and eligible guarantors."""
    def get(self, request):
        from members.models import Member
        member_id = request.GET.get('member_id')
        loan_amount = request.GET.get('amount', '0')
        try:
            member = scope_members(request).get(pk=member_id)
            total_contributions = float(member.total_contributions() or 0)
            loan_amount = float(loan_amount or 0)
            needs_guarantor = loan_amount > total_contributions
            shortfall = max(loan_amount - total_contributions, 0)

            # Eligible guarantors: scoped to same chama, no active/late loan, excluding borrower
            active_loan_ids = scope(request, Loan.objects.filter(
                status__in=['active', 'late']
            )).values_list('member_id', flat=True)
            eligible = scope_members(request).exclude(pk=member.pk).exclude(pk__in=active_loan_ids)
            guarantors = [{'id': m.pk, 'name': m.name, 'phone': m.phone,
                           'contributions': float(m.total_contributions() or 0)}
                          for m in eligible]
            return JsonResponse({
                'total_contributions': total_contributions,
                'needs_guarantor': needs_guarantor,
                'shortfall': shortfall,
                'guarantors': guarantors,
            })
        except Member.DoesNotExist:
            return JsonResponse({'error': 'Member not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)


class CollateralCreateView(TreasurerRequiredMixin, SuccessMessageMixin, CreateView):
    model = Collateral
    form_class = CollateralForm
    template_name = 'loans/collateral_form.html'
    success_message = "Collateral added."

    def dispatch(self, request, *args, **kwargs):
        loan = get_object_or_404(Loan, pk=kwargs['loan_pk'])
        if loan.member.status == 'exited':
            from django.contrib import messages
            messages.error(request, "Cannot modify a loan belonging to an exited member.")
            return redirect('loans:detail', pk=loan.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.loan_id = self.kwargs['loan_pk']
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('loans:detail', kwargs={'pk': self.kwargs['loan_pk']})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['loan'] = Loan.objects.get(pk=self.kwargs['loan_pk'])
        return ctx


class CollateralDeleteView(AdminRequiredMixin, DeleteView):
    model = Collateral
    template_name = 'loans/collateral_confirm_delete.html'

    def get_queryset(self):
        chama = getattr(self.request, 'chama', None)
        if chama:
            return Collateral.objects.filter(loan__member__chama=chama)
        return Collateral.objects.all()

    def get_success_url(self):
        return reverse_lazy('loans:detail', kwargs={'pk': self.object.loan_id})


class GuarantorAddView(TreasurerRequiredMixin, SuccessMessageMixin, CreateView):
    model = LoanGuarantor
    form_class = LoanGuarantorForm
    template_name = 'loans/guarantor_form.html'
    success_message = "Guarantor added."

    def dispatch(self, request, *args, **kwargs):
        loan = get_object_or_404(Loan, pk=kwargs['loan_pk'])
        if loan.member.status == 'exited':
            from django.contrib import messages
            messages.error(request, "Cannot modify a loan belonging to an exited member.")
            return redirect('loans:detail', pk=loan.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['loan'] = Loan.objects.get(pk=self.kwargs['loan_pk'])
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs

    def form_valid(self, form):
        form.instance.loan_id = self.kwargs['loan_pk']
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('loans:detail', kwargs={'pk': self.kwargs['loan_pk']})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['loan'] = Loan.objects.get(pk=self.kwargs['loan_pk'])
        return ctx


class GuarantorDeleteView(TreasurerRequiredMixin, DeleteView):
    model = LoanGuarantor
    template_name = 'loans/guarantor_confirm_delete.html'

    def get_queryset(self):
        chama = getattr(self.request, 'chama', None)
        if chama:
            return LoanGuarantor.objects.filter(loan__member__chama=chama)
        return LoanGuarantor.objects.all()

    def get_success_url(self):
        return reverse_lazy('loans:detail', kwargs={'pk': self.object.loan_id})


class GuarantorsReportView(LoginRequiredMixin, TemplateView):
    template_name = 'loans/guarantors_report.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        chama = getattr(self.request, 'chama', None)
        qs = LoanGuarantor.objects.select_related('guarantor', 'loan__member')
        if chama:
            qs = qs.filter(loan__member__chama=chama)
        ctx['guarantors'] = qs.order_by('guarantor__name')
        return ctx


class EmergencyLoanListView(LoginRequiredMixin, ListView):
    model = Loan
    template_name = 'loans/emergency_loan_list.html'
    context_object_name = 'loans'
    paginate_by = 20

    def get_queryset(self):
        qs = scope(self.request, Loan.objects.filter(loan_type='emergency')).select_related('member')
        status = self.request.GET.get('status')
        q = self.request.GET.get('q', '').strip()
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(member__name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = scope(self.request, Loan.objects.filter(loan_type='emergency'))
        ctx['total_issued'] = qs.aggregate(t=Sum('loan_amount'))['t'] or 0
        ctx['active_count'] = qs.filter(status='active').count()
        ctx['cleared_count'] = qs.filter(status='cleared').count()
        ctx['late_count'] = qs.filter(status='late').count()
        ctx['total_balance'] = sum(l.balance for l in qs)
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class EmergencyLoanCreateView(TreasurerRequiredMixin, SuccessMessageMixin, CreateView):
    model = Loan
    form_class = EmergencyLoanForm
    template_name = 'loans/emergency_loan_form.html'
    success_url = reverse_lazy('loans:emergency_list')
    success_message = "Emergency loan issued successfully."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs

    def form_valid(self, form):
        form.instance.loan_type = 'emergency'
        form.instance.duration_months = 1
        return super().form_valid(form)


class LoanSchedulePrintView(LoginRequiredMixin, DetailView):
    model = Loan
    template_name = 'loans/loan_schedule_print.html'
    context_object_name = 'loan'

    def get_queryset(self):
        return scope(self.request, Loan.objects.all())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['schedule'] = self.object.get_schedule()
        return ctx


class LoanScheduleCSVView(LoginRequiredMixin, View):
    def get(self, request, pk):
        import csv
        from django.http import HttpResponse
        loan = get_object_or_404(scope(request, Loan.objects.all()), pk=pk)
        schedule = loan.get_schedule()

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="loan_{pk}_schedule.csv"'
        writer = csv.writer(response)
        writer.writerow(['Month', 'Opening Balance', 'Rate (%)', 'Interest',
                         'Principal', 'Total Payment', 'Closing Balance'])
        for row in schedule:
            writer.writerow([
                row['month'], row['opening_balance'], row['rate'],
                row['interest'], row['principal'],
                row['total_payment'], row['closing_balance'],
            ])
        writer.writerow([])
        writer.writerow(['', '', 'TOTALS', loan.interest_amount,
                         loan.loan_amount, loan.total_payable, ''])
        return response


class LoanListPrintView(LoginRequiredMixin, View):
    def get(self, request):
        from django.shortcuts import render
        qs = scope(request, Loan.objects.select_related('member').order_by('-date_taken'))
        status = request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        total_issued = sum(l.loan_amount for l in qs)
        total_paid = sum(l.amount_paid for l in qs)
        total_balance = sum(l.balance for l in qs)
        return render(request, 'loans/loan_list_print.html', {
            'loans': qs,
            'total_issued': total_issued,
            'total_paid': total_paid,
            'total_balance': total_balance,
        })


class LoanListCSVView(LoginRequiredMixin, View):
    def get(self, request):
        from core.exports import csv_response
        qs = scope(request, Loan.objects.select_related('member').order_by('-date_taken'))
        status = request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        headers = ['Member', 'Amount', 'Duration (months)', 'Interest', 'Total Payable',
                   'Amount Paid', 'Balance', 'Date Taken', 'Due Date', 'Status']
        rows = [[
            l.member.name, l.loan_amount, l.duration_months, l.interest_amount,
            l.total_payable, l.amount_paid, l.balance,
            l.date_taken, l.due_date or '', l.get_status_display(),
        ] for l in qs]
        return csv_response('loans.csv', headers, rows)
