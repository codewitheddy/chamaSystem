from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum
from decimal import Decimal

from .models import Investment, InvestmentTransaction, InvestmentDocument
from .forms import (InvestmentForm, InvestmentUpdateForm,
                    InvestmentTransactionForm, InvestmentDocumentForm)


def _get_investment(request, pk):
    from tenants.scoping import scope
    return get_object_or_404(scope(request, Investment.objects.all()), pk=pk)


def _treasurer(user):
    p = getattr(user, 'profile', None)
    if not p or p.role not in ('admin', 'treasurer'):
        raise PermissionDenied


def _admin(user):
    p = getattr(user, 'profile', None)
    if not p or p.role != 'admin':
        raise PermissionDenied


class InvestmentDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        from tenants.scoping import scope
        investments = scope(request, Investment.objects.all())
        active = investments.filter(status=Investment.STATUS_ACTIVE)
        exited = investments.filter(status=Investment.STATUS_EXITED)

        total_invested = investments.aggregate(t=Sum('amount_invested'))['t'] or Decimal('0')
        total_current = sum(
            (i.current_value or i.amount_invested) for i in active
        )
        total_returns = sum(i.total_returns for i in investments)
        total_exit = exited.aggregate(t=Sum('exit_amount'))['t'] or Decimal('0')

        # Portfolio breakdown by type
        by_type = {}
        for inv in active:
            label = inv.get_investment_type_display()
            by_type[label] = by_type.get(label, Decimal('0')) + (inv.current_value or inv.amount_invested)

        return render(request, 'investments/dashboard.html', {
            'investments': investments,
            'active_count': active.count(),
            'exited_count': exited.count(),
            'total_invested': total_invested,
            'total_current': total_current,
            'total_returns': total_returns,
            'total_exit': total_exit,
            'unrealised_gain': total_current - sum(i.amount_invested for i in active),
            'by_type': by_type,
        })


class InvestmentListView(LoginRequiredMixin, View):
    def get(self, request):
        from tenants.scoping import scope
        qs = scope(request, Investment.objects.all())
        status = request.GET.get('status', '')
        inv_type = request.GET.get('type', '')
        if status:
            qs = qs.filter(status=status)
        if inv_type:
            qs = qs.filter(investment_type=inv_type)
        return render(request, 'investments/investment_list.html', {
            'investments': qs,
            'filter_status': status,
            'filter_type': inv_type,
            'status_choices': Investment.STATUS_CHOICES,
            'type_choices': Investment.TYPE_CHOICES,
        })


class InvestmentDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        inv = _get_investment(request, pk)
        tx_form = InvestmentTransactionForm()
        doc_form = InvestmentDocumentForm()
        return render(request, 'investments/investment_detail.html', {
            'inv': inv,
            'transactions': inv.transactions.order_by('-date'),
            'documents': inv.documents.order_by('-uploaded_at'),
            'tx_form': tx_form,
            'doc_form': doc_form,
        })


class InvestmentCreateView(LoginRequiredMixin, View):
    def get(self, request):
        _treasurer(request.user)
        return render(request, 'investments/investment_form.html',
                      {'form': InvestmentForm(), 'title': 'Add Investment'})

    def post(self, request):
        _treasurer(request.user)
        form = InvestmentForm(request.POST)
        if form.is_valid():
            inv = form.save(commit=False)
            inv.created_by = request.user
            inv.chama = getattr(request, 'chama', None)
            inv.save()
            # Post initial capital injection to ledger
            InvestmentTransaction.objects.create(
                investment=inv,
                tx_type=InvestmentTransaction.TYPE_INJECTION,
                amount=inv.amount_invested,
                date=inv.date_invested,
                description='Initial capital investment',
                created_by=request.user,
            )
            messages.success(request, f"Investment '{inv.name}' added.")
            return redirect('investments:detail', pk=inv.pk)
        return render(request, 'investments/investment_form.html',
                      {'form': form, 'title': 'Add Investment'})


class InvestmentUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        _treasurer(request.user)
        inv = _get_investment(request, pk)
        form = InvestmentUpdateForm(instance=inv)
        return render(request, 'investments/investment_form.html',
                      {'form': form, 'title': f'Edit — {inv.name}', 'inv': inv})

    def post(self, request, pk):
        _treasurer(request.user)
        inv = _get_investment(request, pk)
        form = InvestmentUpdateForm(request.POST, instance=inv)
        if form.is_valid():
            form.save()
            messages.success(request, "Investment updated.")
            return redirect('investments:detail', pk=pk)
        return render(request, 'investments/investment_form.html',
                      {'form': form, 'title': f'Edit — {inv.name}', 'inv': inv})


class TransactionAddView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _treasurer(request.user)
        inv = _get_investment(request, pk)
        form = InvestmentTransactionForm(request.POST)
        if form.is_valid():
            tx = form.save(commit=False)
            tx.investment = inv
            tx.created_by = request.user
            tx.save()
            messages.success(request, f"{tx.get_tx_type_display()} of KES {tx.amount:,.2f} recorded.")
        else:
            messages.error(request, "Invalid transaction data.")
        return redirect('investments:detail', pk=pk)


class TransactionDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _admin(request.user)
        chama = getattr(request, 'chama', None)
        if chama:
            tx = get_object_or_404(InvestmentTransaction, pk=pk, investment__chama=chama)
        else:
            tx = get_object_or_404(InvestmentTransaction, pk=pk)
        inv_pk = tx.investment_id
        tx.delete()
        messages.success(request, "Transaction deleted.")
        return redirect('investments:detail', pk=inv_pk)


class DocumentUploadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _treasurer(request.user)
        inv = _get_investment(request, pk)
        form = InvestmentDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.investment = inv
            doc.uploaded_by = request.user
            doc.save()
            messages.success(request, "Document uploaded.")
        return redirect('investments:detail', pk=pk)


class DocumentDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _admin(request.user)
        chama = getattr(request, 'chama', None)
        if chama:
            doc = get_object_or_404(InvestmentDocument, pk=pk, investment__chama=chama)
        else:
            doc = get_object_or_404(InvestmentDocument, pk=pk)
        inv_pk = doc.investment_id
        doc.file.delete(save=False)
        doc.delete()
        messages.success(request, "Document deleted.")
        return redirect('investments:detail', pk=inv_pk)


class InvestmentListPrintView(LoginRequiredMixin, View):
    def get(self, request):
        from tenants.scoping import scope
        qs = scope(request, Investment.objects.all())
        total_invested = qs.aggregate(t=Sum('amount_invested'))['t'] or Decimal('0')
        total_current = sum((i.current_value or i.amount_invested) for i in qs)
        return render(request, 'investments/investment_list_print.html', {
            'investments': qs,
            'total_invested': total_invested,
            'total_current': total_current,
        })


class InvestmentListCSVView(LoginRequiredMixin, View):
    def get(self, request):
        from core.exports import csv_response
        from tenants.scoping import scope
        qs = scope(request, Investment.objects.all())
        headers = ['Name', 'Type', 'Status', 'Amount Invested', 'Current Value',
                   'Total Returns', 'Net Gain', 'ROI %', 'Date Invested', 'Location']
        rows = [[
            i.name, i.get_investment_type_display(), i.get_status_display(),
            i.amount_invested, i.current_value or '',
            i.total_returns, i.net_gain, i.roi_percent,
            i.date_invested, i.location or '',
        ] for i in qs]
        return csv_response('investments.csv', headers, rows)
