from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Sum
from members.models import Member
from contributions.models import Contribution
from loans.models import Loan
from payments.models import Payment


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        # Staff/superusers belong in the superadmin panel, not a chama dashboard
        if request.user.is_authenticated and request.user.is_staff:
            from django.shortcuts import redirect
            return redirect('tenants:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from datetime import date
        chama = getattr(self.request, 'chama', None)

        # Scope all querysets to the current chama
        def _members():
            qs = Member.objects
            return qs.filter(chama=chama) if chama else qs.all()

        def _contributions():
            qs = Contribution.objects
            return qs.filter(member__chama=chama) if chama else qs.all()

        def _loans():
            qs = Loan.objects
            return qs.filter(member__chama=chama) if chama else qs.all()

        def _payments():
            qs = Payment.objects
            return qs.filter(member__chama=chama) if chama else qs.all()

        # Auto-mark overdue loans
        _loans().filter(status='active', due_date__lt=date.today()).update(status='late')

        ctx = super().get_context_data(**kwargs)

        members_qs = _members()
        loans_qs = _loans()
        contributions_qs = _contributions()

        total_members = members_qs.filter(status=Member.STATUS_ACTIVE).count()
        exited_members = members_qs.filter(status=Member.STATUS_EXITED).count()
        disabled_members = members_qs.filter(status=Member.STATUS_DISABLED).count()
        total_exit_payout = members_qs.filter(
            status=Member.STATUS_EXITED,
            exit_settlement_amount__isnull=False
        ).aggregate(t=Sum('exit_settlement_amount'))['t'] or 0

        total_contributions = contributions_qs.aggregate(t=Sum('amount'))['t'] or 0
        total_reg_fees = members_qs.aggregate(t=Sum('registration_fee'))['t'] or 0
        total_loans_given = loans_qs.aggregate(t=Sum('loan_amount'))['t'] or 0
        total_interest_projected = loans_qs.aggregate(t=Sum('interest_amount'))['t'] or 0
        total_interest_collected = loans_qs.filter(status='cleared').aggregate(t=Sum('interest_amount'))['t'] or 0
        total_loan_balance = sum(l.balance for l in loans_qs.filter(status__in=['active', 'late']))
        total_loan_paid = loans_qs.aggregate(t=Sum('amount_paid'))['t'] or 0

        # Other income (bank interest, dividends, grants, etc.)
        from accounting.models import OtherIncome, Expense
        other_income_qs = OtherIncome.objects.filter(is_voided=False)
        if chama:
            other_income_qs = other_income_qs.filter(chama=chama)
        total_other_income = other_income_qs.aggregate(t=Sum('amount'))['t'] or 0

        # Investment returns (income, dividends, exit proceeds — NOT capital injections)
        from investments.models import InvestmentTransaction
        inv_return_types = [
            InvestmentTransaction.TYPE_INCOME,
            InvestmentTransaction.TYPE_DIVIDEND,
            InvestmentTransaction.TYPE_EXIT,
        ]
        inv_tx_qs = InvestmentTransaction.objects.filter(tx_type__in=inv_return_types)
        if chama:
            inv_tx_qs = inv_tx_qs.filter(investment__chama=chama)
        total_investment_returns = inv_tx_qs.aggregate(t=Sum('amount'))['t'] or 0

        # Total expenses
        expense_qs = Expense.objects.filter(is_voided=False)
        if chama:
            expense_qs = expense_qs.filter(chama=chama)
        total_expenses = expense_qs.aggregate(t=Sum('amount'))['t'] or 0

        # Total share capital
        from shares.models import ShareAccount
        share_qs = ShareAccount.objects.filter(member__chama=chama) if chama else ShareAccount.objects.all()
        from decimal import Decimal
        from shares.models import ShareConfig
        share_config = ShareConfig.get(chama=chama)
        total_shares_held = share_qs.aggregate(t=Sum('shares_held'))['t'] or 0
        total_share_capital = Decimal(str(total_shares_held)) * share_config.par_value

        total_income = total_contributions + total_reg_fees + total_interest_collected + total_other_income + total_investment_returns

        import json
        today_year = date.today().year
        contrib_by_month = (
            contributions_qs.filter(year=today_year)
            .values('month').annotate(total=Sum('amount')).order_by('month')
        )
        contrib_chart = [0] * 12
        for row in contrib_by_month:
            contrib_chart[row['month'] - 1] = float(row['total'])

        from django.db.models.functions import ExtractMonth as _ExtractMonth
        loan_by_month = (
            loans_qs.filter(date_taken__year=today_year)
            .annotate(month=_ExtractMonth('date_taken'))
            .values('month').annotate(total=Sum('loan_amount')).order_by('month')
        )
        loan_chart = [0] * 12
        for row in loan_by_month:
            if row['month']:
                loan_chart[row['month'] - 1] = float(row['total'])

        ctx.update({
            'chama': chama,
            'total_members': total_members,
            'exited_members': exited_members,
            'disabled_members': disabled_members,
            'total_exit_payout': total_exit_payout,
            'total_contributions': total_contributions,
            'total_reg_fees': total_reg_fees,
            'total_loans_given': total_loans_given,
            'total_interest_projected': total_interest_projected,
            'total_interest_collected': total_interest_collected,
            'total_loan_balance': total_loan_balance,
            'total_loan_paid': total_loan_paid,
            'total_other_income': total_other_income,
            'total_investment_returns': total_investment_returns,
            'total_expenses': total_expenses,
            'total_share_capital': total_share_capital,
            'total_income': total_income,
            'recent_contributions': contributions_qs.select_related('member').order_by('-date')[:5],
            'recent_loans': loans_qs.select_related('member').order_by('-date_taken')[:5],
            'recent_payments': _payments().select_related('member').order_by('-date')[:5],
            'contrib_chart_data': json.dumps(contrib_chart),
            'loan_chart_data': json.dumps(loan_chart),
            'chart_year': today_year,
        })
        return ctx
