from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.views import View
from django.urls import reverse_lazy
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from decimal import Decimal
from datetime import date
import calendar

from .models import Transaction, Expense, OtherIncome
from .forms import ExpenseForm, ManualTransactionForm, OtherIncomeForm
from accounts.mixins import TreasurerRequiredMixin, AdminRequiredMixin
from tenants.scoping import scope


def _totals(qs):
    credits = qs.filter(direction=Transaction.CREDIT).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    debits  = qs.filter(direction=Transaction.DEBIT).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    return credits, debits


class AccountingDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'accounting/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from tenants.scoping import scope_members
        from contributions.models import Contribution
        from loans.models import Loan
        from payments.models import Payment
        from meetings.models import MeetingPenalty

        all_tx = scope(self.request, Transaction.objects.all())
        credits, debits = _totals(all_tx)

        ctx['total_credits'] = credits
        ctx['total_debits']  = debits
        ctx['fund_balance']  = credits - debits

        # Registration fees — read directly from Member model (never posted as transactions)
        members = scope_members(self.request)
        ctx['total_reg_fees'] = members.aggregate(
            t=Sum('registration_fee'))['t'] or Decimal('0')

        # Contributions — prefer transaction ledger, fall back to Contribution model
        tx_contribs = all_tx.filter(
            category=Transaction.CAT_CONTRIBUTION).aggregate(t=Sum('amount'))['t']
        if tx_contribs:
            ctx['total_contributions'] = tx_contribs
        else:
            ctx['total_contributions'] = scope(
                self.request, Contribution.objects.filter(is_voided=False)
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # Loan repayments
        tx_repayments = all_tx.filter(
            category=Transaction.CAT_LOAN_REPAYMENT).aggregate(t=Sum('amount'))['t']
        if tx_repayments:
            ctx['total_repayments'] = tx_repayments
        else:
            ctx['total_repayments'] = scope(
                self.request, Payment.objects.filter(is_voided=False)
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # Interest earned
        tx_interest = all_tx.filter(
            category=Transaction.CAT_INTEREST).aggregate(t=Sum('amount'))['t']
        if tx_interest:
            ctx['total_interest'] = tx_interest
        else:
            ctx['total_interest'] = scope(
                self.request, Loan.objects.all()
            ).aggregate(t=Sum('interest_amount'))['t'] or Decimal('0')

        # Penalties
        ctx['total_penalties'] = all_tx.filter(
            category=Transaction.CAT_PENALTY).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        if not ctx['total_penalties']:
            ctx['total_penalties'] = scope(
                self.request,
                MeetingPenalty.objects.filter(is_voided=False, paid=True)
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # Loans issued
        ctx['total_loans_issued'] = all_tx.filter(
            category=Transaction.CAT_LOAN_ISSUED).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        if not ctx['total_loans_issued']:
            ctx['total_loans_issued'] = scope(
                self.request, Loan.objects.all()
            ).aggregate(t=Sum('loan_amount'))['t'] or Decimal('0')

        # Expenses
        ctx['total_expenses'] = all_tx.filter(
            category=Transaction.CAT_EXPENSE).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        if not ctx['total_expenses']:
            from accounting.models import Expense
            ctx['total_expenses'] = scope(
                self.request, Expense.objects.filter(is_voided=False)
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # Other income (bank interest, dividends, grants, etc.)
        ctx['total_other_income'] = scope(
            self.request, OtherIncome.objects.filter(is_voided=False)
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # If the ledger is empty entirely, compute fund_balance from raw models
        if credits == 0 and debits == 0:
            ctx['fund_balance'] = (
                ctx['total_contributions'] +
                ctx['total_reg_fees'] +
                ctx['total_repayments'] +
                ctx['total_interest'] +
                ctx['total_penalties'] +
                ctx['total_other_income'] -
                ctx['total_loans_issued'] -
                ctx['total_expenses']
            )
            ctx['total_credits'] = (
                ctx['total_contributions'] +
                ctx['total_reg_fees'] +
                ctx['total_repayments'] +
                ctx['total_interest'] +
                ctx['total_penalties'] +
                ctx['total_other_income']
            )
            ctx['total_debits'] = ctx['total_loans_issued'] + ctx['total_expenses']

        today = date.today()
        monthly = []
        for i in range(11, -1, -1):
            m = today.month - i
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            month_tx = all_tx.filter(date__year=y, date__month=m)
            mc, md = _totals(month_tx)

            # If transaction ledger is empty, build from source models
            if mc == 0 and md == 0:
                from contributions.models import Contribution as Contrib
                from payments.models import Payment as Pay
                from accounting.models import Expense as Exp
                from loans.models import Loan as L
                from tenants.scoping import scope_members

                mc = scope(self.request, Contrib.objects.filter(
                    is_voided=False, date__year=y, date__month=m
                )).aggregate(t=Sum('amount'))['t'] or Decimal('0')
                mc += scope(self.request, Pay.objects.filter(
                    is_voided=False, date__year=y, date__month=m
                )).aggregate(t=Sum('amount'))['t'] or Decimal('0')

                md = scope(self.request, Exp.objects.filter(
                    is_voided=False, date__year=y, date__month=m
                )).aggregate(t=Sum('amount'))['t'] or Decimal('0')
                md += scope(self.request, L.objects.filter(
                    date_taken__year=y, date_taken__month=m
                )).aggregate(t=Sum('loan_amount'))['t'] or Decimal('0')

            monthly.append({
                'label': f"{calendar.month_abbr[m]} {y}",
                'credits': float(mc),
                'debits': float(md),
                'net': float(mc - md),
            })
        ctx['monthly'] = monthly
        ctx['recent'] = scope(self.request, Transaction.objects.select_related('member').order_by('-date', '-pk'))[:15]

        # If ledger is empty, build recent from contributions + payments
        if not ctx['recent']:
            from contributions.models import Contribution as Contrib
            from payments.models import Payment as Pay
            recent_items = []
            for c in scope(self.request, Contrib.objects.select_related('member').filter(
                    is_voided=False).order_by('-date'))[:8]:
                recent_items.append({
                    'date': c.date,
                    'description': f"Contribution — {c.member.name}",
                    'amount': c.amount,
                    'direction': 'credit',
                })
            for p in scope(self.request, Pay.objects.select_related('member').filter(
                    is_voided=False).order_by('-date'))[:7]:
                recent_items.append({
                    'date': p.date,
                    'description': f"Loan repayment — {p.member.name}",
                    'amount': p.amount,
                    'direction': 'credit',
                })
            recent_items.sort(key=lambda x: x['date'], reverse=True)
            ctx['recent_raw'] = recent_items[:15]
        return ctx


class LedgerView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'accounting/ledger.html'
    context_object_name = 'transactions'
    paginate_by = 40

    def get_queryset(self):
        qs = scope(self.request, Transaction.objects.select_related('member'))
        cat       = self.request.GET.get('category', '')
        direction = self.request.GET.get('direction', '')
        date_from = self.request.GET.get('date_from', '')
        date_to   = self.request.GET.get('date_to', '')
        q         = self.request.GET.get('q', '').strip()
        if cat:       qs = qs.filter(category=cat)
        if direction: qs = qs.filter(direction=direction)
        if date_from: qs = qs.filter(date__gte=date_from)
        if date_to:   qs = qs.filter(date__lte=date_to)
        if q:         qs = qs.filter(Q(description__icontains=q) | Q(member__name__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        credits, debits = _totals(qs)
        ctx['filtered_credits'] = credits
        ctx['filtered_debits']  = debits
        ctx['filtered_net']     = credits - debits
        ctx['category_choices'] = Transaction.CATEGORY_CHOICES
        ctx['filter_category']  = self.request.GET.get('category', '')
        ctx['filter_direction'] = self.request.GET.get('direction', '')
        ctx['filter_date_from'] = self.request.GET.get('date_from', '')
        ctx['filter_date_to']   = self.request.GET.get('date_to', '')
        ctx['filter_q']         = self.request.GET.get('q', '')
        return ctx


class ExpenseListView(LoginRequiredMixin, ListView):
    model = Expense
    template_name = 'accounting/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 30

    def get_queryset(self):
        return scope(self.request, Expense.objects.all())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_expenses'] = scope(self.request, Expense.objects.filter(
            is_voided=False)).aggregate(t=Sum('amount'))['t'] or 0
        return ctx


class ExpenseCreateView(TreasurerRequiredMixin, View):
    template_name = 'accounting/expense_form.html'

    def get(self, request):
        chama = getattr(request, 'chama', None)
        form = ExpenseForm()
        availability = get_available_by_source(chama)
        return render(request, self.template_name, {
            'form': form,
            'availability': availability,
        })

    def post(self, request):
        chama = getattr(request, 'chama', None)
        form = ExpenseForm(request.POST)
        availability = get_available_by_source(chama)

        if form.is_valid():
            source = form.cleaned_data['fund_source']
            amount = form.cleaned_data['amount']

            # ── Fund availability check for internal sources ───────────────
            if source in Expense.INTERNAL_SOURCES:
                available = availability.get(source, Decimal('0'))
                if amount > available:
                    source_label = dict(Expense.SOURCE_CHOICES).get(source, source)
                    form.add_error(
                        'amount',
                        f"Insufficient funds in {source_label}. "
                        f"Available: KES {available:,.2f}"
                    )
                    return render(request, self.template_name, {
                        'form': form,
                        'availability': availability,
                    })

            # ── Save expense ──────────────────────────────────────────────
            expense = form.save(commit=False)
            expense.chama = chama
            expense.save()

            # ── Post debit transaction for internal sources ────────────────
            if source in Expense.INTERNAL_SOURCES:
                Transaction.objects.create(
                    chama=chama,
                    date=expense.date,
                    category=Transaction.CAT_EXPENSE,
                    direction=Transaction.DEBIT,
                    amount=expense.amount,
                    description=f"Expense ({expense.get_fund_source_display()}): {expense.description}",
                    reference=f"expense:{expense.pk}",
                    is_manual=False,
                )

            messages.success(request, "Expense recorded.")
            return redirect('accounting:expenses')

        return render(request, self.template_name, {
            'form': form,
            'availability': availability,
        })


class ExpenseUpdateView(TreasurerRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = 'accounting/expense_form.html'
    success_url = reverse_lazy('accounting:expenses')
    success_message = "Expense updated."

    def form_valid(self, form):
        # Ensure chama is set on update too
        if not form.instance.chama_id:
            form.instance.chama = getattr(self.request, 'chama', None)
        return super().form_valid(form)


class ExpenseVoidView(AdminRequiredMixin, View):
    """Void an expense — keeps the record, removes from totals, reverses ledger entry."""
    def post(self, request, pk):
        chama = getattr(request, 'chama', None)
        expense = get_object_or_404(Expense, pk=pk, chama=chama)
        if expense.is_voided:
            messages.warning(request, "Already voided.")
            return redirect('accounting:expenses')
        reason = request.POST.get('void_reason', '').strip() or 'Voided by admin'
        expense.is_voided = True
        expense.void_reason = reason
        expense.save()

        # Reverse the debit transaction that was posted when this expense was recorded
        Transaction.objects.filter(
            chama=chama,
            reference=f"expense:{expense.pk}",
            category=Transaction.CAT_EXPENSE,
            direction=Transaction.DEBIT,
        ).delete()

        messages.success(request, "Expense voided and ledger reversed.")
        return redirect('accounting:expenses')


class ManualTransactionCreateView(AdminRequiredMixin, SuccessMessageMixin, CreateView):
    model = Transaction
    form_class = ManualTransactionForm
    template_name = 'accounting/manual_transaction_form.html'
    success_url = reverse_lazy('accounting:ledger')
    success_message = "Transaction posted."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs

    def form_valid(self, form):
        form.instance.is_manual = True
        form.instance.chama = getattr(self.request, 'chama', None)
        return super().form_valid(form)


class ManualTransactionDeleteView(AdminRequiredMixin, DeleteView):
    model = Transaction
    template_name = 'accounting/transaction_confirm_delete.html'
    success_url = reverse_lazy('accounting:ledger')

    def get_queryset(self):
        return Transaction.objects.filter(is_manual=True)


class LedgerPrintView(LoginRequiredMixin, View):
    def get(self, request):
        qs = scope(request, Transaction.objects.select_related('member'))
        cat = request.GET.get('category', '')
        direction = request.GET.get('direction', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        q = request.GET.get('q', '').strip()
        if cat:       qs = qs.filter(category=cat)
        if direction: qs = qs.filter(direction=direction)
        if date_from: qs = qs.filter(date__gte=date_from)
        if date_to:   qs = qs.filter(date__lte=date_to)
        if q:         qs = qs.filter(Q(description__icontains=q) | Q(member__name__icontains=q))
        credits, debits = _totals(qs)
        return render(request, 'accounting/ledger_print.html', {
            'transactions': qs,
            'filtered_credits': credits,
            'filtered_debits': debits,
            'filtered_net': credits - debits,
        })


class LedgerCSVView(LoginRequiredMixin, View):
    def get(self, request):
        from core.exports import csv_response
        qs = scope(request, Transaction.objects.select_related('member'))
        cat = request.GET.get('category', '')
        direction = request.GET.get('direction', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        if cat:       qs = qs.filter(category=cat)
        if direction: qs = qs.filter(direction=direction)
        if date_from: qs = qs.filter(date__gte=date_from)
        if date_to:   qs = qs.filter(date__lte=date_to)
        headers = ['Date', 'Category', 'Direction', 'Amount', 'Description', 'Member', 'Reference']
        rows = [[
            tx.date, tx.get_category_display(), tx.get_direction_display(),
            tx.amount, tx.description, tx.member.name if tx.member else '',
            tx.reference or '',
        ] for tx in qs]
        return csv_response('ledger.csv', headers, rows)


# ── Fund availability helper ──────────────────────────────────────────────────

def get_available_by_source(chama):
    """
    Returns a dict of available balance per internal fund source.
    Keys: 'contributions', 'registration', 'other_income', plus 'total' (overall cash balance).
    Each value is the total collected minus expenses already drawn from that source.
    """
    from contributions.models import Contribution
    from loans.models import Loan
    from payments.models import Payment
    from meetings.models import MeetingPenalty
    from members.models import Member

    if chama is None:
        zero = Decimal('0')
        return {k: zero for k in ('contributions', 'registration', 'other_income', 'total')}

    # ── Income per pool ───────────────────────────────────────────────────────
    contributions = Contribution.objects.filter(
        member__chama=chama, is_voided=False
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    repayments = Payment.objects.filter(
        member__chama=chama, is_voided=False
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    penalties = MeetingPenalty.objects.filter(
        member__chama=chama, is_voided=False, paid=True
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    reg_fees = Member.objects.filter(
        chama=chama
    ).aggregate(t=Sum('registration_fee'))['t'] or Decimal('0')

    other_income = OtherIncome.objects.filter(
        chama=chama, is_voided=False
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    # ── Expenses already drawn per source ────────────────────────────────────
    def _spent(source):
        return Expense.objects.filter(
            chama=chama, is_voided=False, fund_source=source
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    spent_contributions = _spent(Expense.SOURCE_CONTRIBUTIONS)
    spent_registration  = _spent(Expense.SOURCE_REGISTRATION)
    spent_other_income  = _spent(Expense.SOURCE_OTHER_INCOME)

    # Loans reduce the contributions pool
    loans_issued = Loan.objects.filter(
        member__chama=chama
    ).aggregate(t=Sum('loan_amount'))['t'] or Decimal('0')

    from investments.models import InvestmentTransaction
    inv_injections = InvestmentTransaction.objects.filter(
        investment__chama=chama, tx_type=InvestmentTransaction.TYPE_INJECTION
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    inv_returns = InvestmentTransaction.objects.filter(
        investment__chama=chama,
        tx_type__in=[
            InvestmentTransaction.TYPE_INCOME,
            InvestmentTransaction.TYPE_DIVIDEND,
            InvestmentTransaction.TYPE_EXIT,
        ]
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    avail_contributions = (
        contributions + repayments + penalties
        - loans_issued - inv_injections + inv_returns
        - spent_contributions
    )
    avail_registration  = reg_fees - spent_registration
    avail_other_income  = other_income - spent_other_income

    total = avail_contributions + avail_registration + avail_other_income

    return {
        'contributions': max(avail_contributions, Decimal('0')),
        'registration':  max(avail_registration,  Decimal('0')),
        'other_income':  max(avail_other_income,  Decimal('0')),
        'total':         max(total, Decimal('0')),
        # raw (may be negative — useful for display)
        'contributions_raw': avail_contributions,
        'registration_raw':  avail_registration,
        'other_income_raw':  avail_other_income,
    }


def get_fund_balance(request):
    """
    Returns (total_fund, active_loans_outstanding, available_for_loans).
    total_fund = all money collected - all money paid out (expenses, disbursed loans net of repayments)
    available_for_loans = total_fund - active loan balances outstanding
    """
    from contributions.models import Contribution
    from loans.models import Loan
    from payments.models import Payment
    from meetings.models import MeetingPenalty
    from accounting.models import Expense, OtherIncome
    from decimal import Decimal

    # Total money in
    contribs = scope(request, Contribution.objects.filter(is_voided=False)
                     ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    repayments = scope(request, Payment.objects.filter(is_voided=False)
                       ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    penalties = scope(request, MeetingPenalty.objects.filter(is_voided=False, paid=True)
                      ).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    from tenants.scoping import scope_members
    reg_fees = scope_members(request).aggregate(t=Sum('registration_fee'))['t'] or Decimal('0')
    other_income = scope(request, OtherIncome.objects.filter(is_voided=False)
                         ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    # Investment returns (income, dividends, exit proceeds)
    from investments.models import InvestmentTransaction
    inv_return_types = [
        InvestmentTransaction.TYPE_INCOME,
        InvestmentTransaction.TYPE_DIVIDEND,
        InvestmentTransaction.TYPE_EXIT,
    ]
    investment_returns = scope(request, InvestmentTransaction.objects.filter(
        tx_type__in=inv_return_types)
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    # Capital injected into investments (money that left the fund)
    investment_injections = scope(request, InvestmentTransaction.objects.filter(
        tx_type=InvestmentTransaction.TYPE_INJECTION)
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

    # Total money out
    expenses = scope(request, Expense.objects.filter(
        is_voided=False,
        fund_source__in=[Expense.SOURCE_CONTRIBUTIONS, Expense.SOURCE_REGISTRATION]
    )).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    loans_issued = scope(request, Loan.objects.all()
                         ).aggregate(t=Sum('loan_amount'))['t'] or Decimal('0')

    # Active loan balances (money still owed to the group)
    active_loans = scope(request, Loan.objects.filter(status__in=['active', 'late']))
    active_loan_balance = sum(l.balance for l in active_loans)

    # Cash balance = all inflows - all outflows
    cash_balance = (contribs + reg_fees + penalties + repayments +
                    other_income + investment_returns -
                    expenses - loans_issued - investment_injections)

    return {
        'cash_balance': cash_balance,
        'active_loan_balance': Decimal(str(active_loan_balance)),
        'available_for_new_loans': cash_balance,
        'total_contributions': contribs,
        'total_repayments': repayments,
        'total_expenses': expenses,
        'total_other_income': other_income,
        'total_investment_returns': investment_returns,
        'total_loans_issued': loans_issued,
    }


# ── Year-End Payout ───────────────────────────────────────────────────────────

class YearEndPayoutListView(AdminRequiredMixin, View):
    def get(self, request):
        from .models import YearEndPayout
        payouts = scope(request, YearEndPayout.objects.all())
        fund = get_fund_balance(request)
        return render(request, 'accounting/year_end_list.html', {
            'payouts': payouts,
            'fund': fund,
        })


class YearEndPayoutCreateView(AdminRequiredMixin, View):
    """Preview and create a year-end payout."""
    def get(self, request):
        from .models import YearEndPayout
        from tenants.scoping import scope_members
        from datetime import date

        chama = getattr(request, 'chama', None)
        year = int(request.GET.get('year', date.today().year))

        # Check if payout already exists for this year
        existing = YearEndPayout.objects.filter(chama=chama, year=year).first()
        if existing:
            messages.warning(request, f"A payout for {year} already exists.")
            return redirect('accounting:year_end_detail', pk=existing.pk)

        members = scope_members(request).filter(status='active')
        fund = get_fund_balance(request)

        # Calculate per-member breakdown
        from contributions.models import Contribution
        total_contribs = scope(request, Contribution.objects.filter(is_voided=False)
                               ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        member_rows = []
        total_distributed = Decimal('0')
        for m in members:
            ps = m.profit_share()
            loan_bal = Decimal(str(m.total_loan_balance()))
            penalties = Decimal(str(m.unpaid_penalties()))
            net = ps['member_profit'] + Decimal(str(m.total_contributions())) - loan_bal - penalties
            member_rows.append({
                'member': m,
                'contributions': Decimal(str(m.total_contributions())),
                'profit_share': ps['member_profit'],
                'share_pct': ps['member_share_pct'],
                'loan_deduction': loan_bal,
                'penalty_deduction': penalties,
                'net_payout': max(net, Decimal('0')),
            })
            total_distributed += max(net, Decimal('0'))

        return render(request, 'accounting/year_end_create.html', {
            'year': year,
            'member_rows': member_rows,
            'total_distributed': total_distributed,
            'fund': fund,
            'income_pool': member_rows[0]['profit_share'] / member_rows[0]['share_pct'] * 100
            if member_rows and member_rows[0]['share_pct'] else Decimal('0'),
        })

    def post(self, request):
        from .models import YearEndPayout, YearEndPayoutLine
        from tenants.scoping import scope_members
        from datetime import date

        chama = getattr(request, 'chama', None)
        year = int(request.POST.get('year', date.today().year))
        payout_date = request.POST.get('payout_date', date.today().isoformat())
        notes = request.POST.get('notes', '')

        if YearEndPayout.objects.filter(chama=chama, year=year).exists():
            messages.error(request, f"A payout for {year} already exists.")
            return redirect('accounting:year_end_list')

        members = scope_members(request).filter(status='active')
        from contributions.models import Contribution
        total_contribs = scope(request, Contribution.objects.filter(is_voided=False)
                               ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # Calculate income pool
        first_member = members.first()
        income_pool = Decimal('0')
        if first_member:
            ps = first_member.profit_share()
            if ps['member_share_pct'] > 0:
                income_pool = ps['income_pool']

        total_distributed = Decimal('0')
        lines_data = []
        for m in members:
            ps = m.profit_share()
            loan_bal = Decimal(str(m.total_loan_balance()))
            penalties = Decimal(str(m.unpaid_penalties()))
            net = ps['member_profit'] + Decimal(str(m.total_contributions())) - loan_bal - penalties
            net = max(net, Decimal('0'))
            total_distributed += net
            lines_data.append({
                'member': m,
                'contributions': Decimal(str(m.total_contributions())),
                'profit_share': ps['member_profit'],
                'loan_deduction': loan_bal,
                'penalty_deduction': penalties,
                'net_payout': net,
            })

        payout = YearEndPayout.objects.create(
            chama=chama,
            year=year,
            payout_date=payout_date,
            total_contributions=total_contribs,
            total_income_pool=income_pool,
            total_distributed=total_distributed,
            notes=notes,
            created_by=request.user,
        )
        for ld in lines_data:
            YearEndPayoutLine.objects.create(
                payout=payout,
                member=ld['member'],
                contributions=ld['contributions'],
                profit_share=ld['profit_share'],
                loan_deduction=ld['loan_deduction'],
                penalty_deduction=ld['penalty_deduction'],
                net_payout=ld['net_payout'],
            )

        messages.success(request, f"{year} year-end payout created. {len(lines_data)} members.")
        return redirect('accounting:year_end_detail', pk=payout.pk)


class YearEndPayoutDetailView(AdminRequiredMixin, View):
    def get(self, request, pk):
        from .models import YearEndPayout
        payout = get_object_or_404(YearEndPayout, pk=pk)
        return render(request, 'accounting/year_end_detail.html', {'payout': payout})


class YearEndLineMarkPaidView(AdminRequiredMixin, View):
    def post(self, request, pk, line_pk):
        from .models import YearEndPayoutLine
        line = get_object_or_404(YearEndPayoutLine, pk=line_pk, payout_id=pk)
        line.is_paid = True
        line.payment_method = request.POST.get('payment_method', 'mpesa')
        line.payment_ref = request.POST.get('payment_ref', '').strip()
        line.save()
        messages.success(request, f"Payment marked for {line.member.name}.")
        return redirect('accounting:year_end_detail', pk=pk)


# ── Other Income ──────────────────────────────────────────────────────────────

class OtherIncomeListView(TreasurerRequiredMixin, ListView):
    model = OtherIncome
    template_name = 'accounting/other_income_list.html'
    context_object_name = 'incomes'
    paginate_by = 30

    def get_queryset(self):
        return scope(self.request, OtherIncome.objects.all())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total'] = scope(self.request, OtherIncome.objects.filter(
            is_voided=False)).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        return ctx


class OtherIncomeCreateView(TreasurerRequiredMixin, SuccessMessageMixin, CreateView):
    model = OtherIncome
    form_class = OtherIncomeForm
    template_name = 'accounting/other_income_form.html'
    success_url = reverse_lazy('accounting:other_income_list')
    success_message = "Income recorded."

    def form_valid(self, form):
        form.instance.chama = getattr(self.request, 'chama', None)
        return super().form_valid(form)


class OtherIncomeUpdateView(TreasurerRequiredMixin, SuccessMessageMixin, UpdateView):
    model = OtherIncome
    form_class = OtherIncomeForm
    template_name = 'accounting/other_income_form.html'
    success_url = reverse_lazy('accounting:other_income_list')
    success_message = "Income updated."


class OtherIncomeVoidView(AdminRequiredMixin, View):
    def post(self, request, pk):
        income = get_object_or_404(OtherIncome, pk=pk)
        if income.is_voided:
            messages.warning(request, "Already voided.")
            return redirect('accounting:other_income_list')
        income.is_voided = True
        income.void_reason = request.POST.get('void_reason', '').strip() or 'Voided by admin'
        income.save()
        messages.success(request, "Income entry voided.")
        return redirect('accounting:other_income_list')
