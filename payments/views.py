from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .models import Payment
from .forms import PaymentForm, PaymentVoidForm
from accounts.mixins import TreasurerRequiredMixin, AdminRequiredMixin
from tenants.scoping import scope


class PaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = 'payments/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 20

    def get_queryset(self):
        qs = scope(self.request, Payment.objects.select_related('member', 'loan__member'))
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(member__name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class PaymentCreateView(TreasurerRequiredMixin, SuccessMessageMixin, CreateView):
    model = Payment
    form_class = PaymentForm
    template_name = 'payments/payment_form.html'
    success_url = reverse_lazy('payments:list')
    success_message = "Payment recorded. Loan balance updated."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['loan_id'] = self.request.GET.get('loan')
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs

    def form_valid(self, form):
        member = form.cleaned_data['loan'].member
        if member.status == 'exited':
            form.add_error('loan', 'Cannot record a payment for an exited member.')
            return self.form_invalid(form)
        form.instance.member = member
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        loan_id = self.request.GET.get('loan')
        if loan_id:
            from loans.models import Loan
            try:
                ctx['prefilled_loan'] = Loan.objects.get(pk=loan_id)
            except Loan.DoesNotExist:
                pass
        return ctx


class PaymentVoidView(AdminRequiredMixin, View):
    """Void a payment — keeps the record, reverses the loan balance."""
    def get(self, request, pk):
        payment = get_object_or_404(scope(request, Payment.objects.all()), pk=pk)
        if payment.is_voided:
            messages.warning(request, "This payment is already voided.")
            return redirect('payments:list')
        form = PaymentVoidForm()
        return render(request, 'payments/payment_void.html', {
            'payment': payment, 'form': form
        })

    def post(self, request, pk):
        payment = get_object_or_404(scope(request, Payment.objects.all()), pk=pk)
        form = PaymentVoidForm(request.POST)
        if form.is_valid():
            from django.utils import timezone
            payment.is_voided = True
            payment.void_reason = form.cleaned_data['reason']
            payment.voided_by = request.user
            payment.voided_at = timezone.now()
            payment.save()  # signal recalculates loan balance
            messages.success(request, "Payment voided. Loan balance has been reversed.")
            return redirect('payments:list')
        return render(request, 'payments/payment_void.html', {
            'payment': payment, 'form': form
        })


class PaymentListPrintView(LoginRequiredMixin, View):
    def get(self, request):
        from django.db.models import Sum
        from django.shortcuts import render
        qs = scope(request, Payment.objects.select_related('member', 'loan')).order_by('-date')
        q = request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(member__name__icontains=q)
        total = qs.filter(is_voided=False).aggregate(t=Sum('amount'))['t'] or 0
        return render(request, 'payments/payment_list_print.html',
                      {'payments': qs, 'total': total})


class PaymentListCSVView(LoginRequiredMixin, View):
    def get(self, request):
        from core.exports import csv_response
        qs = scope(request, Payment.objects.select_related('member', 'loan')).order_by('-date')
        headers = ['Member', 'Loan Amount', 'Payment', 'Date', 'Notes', 'Status',
                   'Void Reason', 'Created By', 'Voided By', 'Voided At']
        rows = [[
            p.member.name, p.loan.loan_amount, p.amount, p.date, p.notes,
            'Voided' if p.is_voided else 'Valid',
            p.void_reason or '',
            p.created_by.username if p.created_by else '',
            p.voided_by.username if p.voided_by else '',
            p.voided_at.strftime('%Y-%m-%d %H:%M') if p.voided_at else '',
        ] for p in qs]
        return csv_response('payments.csv', headers, rows)
