from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.core.paginator import Paginator
from django.shortcuts import render
from django.db.models import Sum
from decimal import Decimal
from datetime import date

from .models import Account, JournalEntry, JournalLine


def _chama(request):
    return getattr(request, 'chama', None)


def _date_range(request):
    today = date.today()
    date_from = request.GET.get('date_from', date(today.year, 1, 1).isoformat())
    date_to = request.GET.get('date_to', today.isoformat())
    return date_from, date_to


# ── Cashbook ──────────────────────────────────────────────────────────────────

class CashbookView(LoginRequiredMixin, View):
    def get(self, request):
        chama = _chama(request)
        date_from, date_to = _date_range(request)

        cash_account = Account.objects.filter(chama=chama, code='1000').first()
        lines = []
        opening_balance = Decimal('0')
        running = Decimal('0')

        if cash_account:
            # Opening balance = all cash movements before date_from
            pre_qs = JournalLine.objects.filter(
                account=cash_account,
                entry__is_posted=True,
                entry__chama=chama,
                entry__date__lt=date_from,
            )
            pre_debits  = pre_qs.filter(side='debit').aggregate(t=Sum('amount'))['t'] or Decimal('0')
            pre_credits = pre_qs.filter(side='credit').aggregate(t=Sum('amount'))['t'] or Decimal('0')
            opening_balance = pre_debits - pre_credits
            running = opening_balance

            qs = JournalLine.objects.filter(
                account=cash_account,
                entry__is_posted=True,
                entry__chama=chama,
                entry__date__gte=date_from,
                entry__date__lte=date_to,
            ).select_related('entry', 'member').order_by('entry__date', 'entry__pk')

            for line in qs:
                if line.side == 'debit':
                    running += line.amount
                    lines.append({
                        'date': line.entry.date,
                        'ref': line.entry.reference,
                        'description': line.entry.description,
                        'debit': line.amount,
                        'credit': None,
                        'balance': running,
                    })
                else:
                    running -= line.amount
                    lines.append({
                        'date': line.entry.date,
                        'ref': line.entry.reference,
                        'description': line.entry.description,
                        'debit': None,
                        'credit': line.amount,
                        'balance': running,
                    })

        total_in  = sum(l['debit']  for l in lines if l['debit'])
        total_out = sum(l['credit'] for l in lines if l['credit'])

        return render(request, 'ledger/cashbook.html', {
            'lines': lines,
            'opening_balance': opening_balance,
            'total_in': total_in,
            'total_out': total_out,
            'closing_balance': running,
            'date_from': date_from,
            'date_to': date_to,
        })


# ── Journal ───────────────────────────────────────────────────────────────────

class JournalView(LoginRequiredMixin, View):
    def get(self, request):
        chama = _chama(request)
        date_from, date_to = _date_range(request)
        qs = JournalEntry.objects.filter(
            chama=chama,
            is_posted=True,
            date__gte=date_from,
            date__lte=date_to,
        ).prefetch_related('lines__account', 'lines__member').order_by('-date', '-pk')

        paginator = Paginator(qs, 50)
        page = paginator.get_page(request.GET.get('page'))

        return render(request, 'ledger/journal.html', {
            'page_obj': page,
            'entries': page.object_list,
            'total_entries': qs.count(),
            'date_from': date_from,
            'date_to': date_to,
        })


# ── Chart of Accounts ─────────────────────────────────────────────────────────

class ChartOfAccountsView(LoginRequiredMixin, View):
    def get(self, request):
        chama = _chama(request)
        accounts = Account.objects.filter(chama=chama).order_by('code')
        by_type = {}
        for acct in accounts:
            by_type.setdefault(acct.get_account_type_display(), []).append(acct)
        return render(request, 'ledger/coa.html', {
            'by_type': by_type,
            'accounts': accounts,
        })


# ── Trial Balance ─────────────────────────────────────────────────────────────

class TrialBalanceView(LoginRequiredMixin, View):
    def get(self, request):
        chama = _chama(request)
        date_from, date_to = _date_range(request)
        accounts = Account.objects.filter(chama=chama, is_active=True).order_by('code')

        rows = []
        total_debit = Decimal('0')
        total_credit = Decimal('0')

        for acct in accounts:
            bal = acct.balance(date_from=date_from, date_to=date_to)
            if bal == 0:
                continue
            if acct.normal_balance == 'debit':
                rows.append({'account': acct, 'debit': bal, 'credit': None})
                total_debit += bal
            else:
                rows.append({'account': acct, 'debit': None, 'credit': bal})
                total_credit += bal

        return render(request, 'ledger/trial_balance.html', {
            'rows': rows,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'balanced': abs(total_debit - total_credit) < Decimal('0.01'),
            'date_from': date_from,
            'date_to': date_to,
        })


# ── Profit & Loss ─────────────────────────────────────────────────────────────

class ProfitLossView(LoginRequiredMixin, View):
    def get(self, request):
        chama = _chama(request)
        date_from, date_to = _date_range(request)

        income_accounts  = Account.objects.filter(chama=chama, account_type='income',  is_active=True).order_by('code')
        expense_accounts = Account.objects.filter(chama=chama, account_type='expense', is_active=True).order_by('code')

        # Compute balance once per account
        income_rows  = [{'account': a, 'amount': a.balance(date_from, date_to)} for a in income_accounts]
        expense_rows = [{'account': a, 'amount': a.balance(date_from, date_to)} for a in expense_accounts]

        # Filter zero rows
        income_rows  = [r for r in income_rows  if r['amount'] != 0]
        expense_rows = [r for r in expense_rows if r['amount'] != 0]

        total_income   = sum(r['amount'] for r in income_rows)
        total_expenses = sum(r['amount'] for r in expense_rows)
        net_profit     = total_income - total_expenses

        # Add percentage of total to each row
        for r in income_rows:
            r['pct'] = round(float(r['amount'] / total_income * 100), 1) if total_income else 0
        for r in expense_rows:
            r['pct'] = round(float(r['amount'] / total_expenses * 100), 1) if total_expenses else 0

        # Fallback: if ledger is empty, pull from source models
        if not income_rows and not expense_rows:
            from contributions.models import Contribution
            from loans.models import Loan
            from accounting.models import Expense
            from meetings.models import MeetingPenalty
            from tenants.scoping import scope

            contrib_total = scope(request, Contribution.objects.filter(
                is_voided=False, date__gte=date_from, date__lte=date_to
            )).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            interest_total = scope(request, Loan.objects.filter(
                date_taken__gte=date_from, date_taken__lte=date_to
            )).aggregate(t=Sum('interest_amount'))['t'] or Decimal('0')

            penalty_total = scope(request, MeetingPenalty.objects.filter(
                is_voided=False, paid=True,
                meeting__date__gte=date_from, meeting__date__lte=date_to
            )).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            expense_total = scope(request, Expense.objects.filter(
                is_voided=False, date__gte=date_from, date__lte=date_to
            )).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            if contrib_total:
                income_rows.append({'account': type('A', (), {'code': '4000', 'name': 'Contribution Income'})(), 'amount': contrib_total, 'pct': 0})
            if interest_total:
                income_rows.append({'account': type('A', (), {'code': '4100', 'name': 'Interest Income'})(), 'amount': interest_total, 'pct': 0})
            if penalty_total:
                income_rows.append({'account': type('A', (), {'code': '4200', 'name': 'Penalty Income'})(), 'amount': penalty_total, 'pct': 0})
            if expense_total:
                expense_rows.append({'account': type('A', (), {'code': '5000', 'name': 'Operating Expenses'})(), 'amount': expense_total, 'pct': 0})

            total_income   = sum(r['amount'] for r in income_rows)
            total_expenses = sum(r['amount'] for r in expense_rows)
            net_profit     = total_income - total_expenses

            for r in income_rows:
                r['pct'] = round(float(r['amount'] / total_income * 100), 1) if total_income else 0
            for r in expense_rows:
                r['pct'] = round(float(r['amount'] / total_expenses * 100), 1) if total_expenses else 0

        profit_margin = round(float(net_profit / total_income * 100), 1) if total_income else 0

        return render(request, 'ledger/profit_loss.html', {
            'income_rows': income_rows,
            'expense_rows': expense_rows,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
            'date_from': date_from,
            'date_to': date_to,
        })


# ── Balance Sheet ─────────────────────────────────────────────────────────────

class BalanceSheetView(LoginRequiredMixin, View):
    def get(self, request):
        chama = _chama(request)
        as_at = request.GET.get('as_at', date.today().isoformat())

        asset_accounts     = Account.objects.filter(chama=chama, account_type='asset',     is_active=True).order_by('code')
        liability_accounts = Account.objects.filter(chama=chama, account_type='liability', is_active=True).order_by('code')
        equity_accounts    = Account.objects.filter(chama=chama, account_type='equity',    is_active=True).order_by('code')
        income_accounts    = Account.objects.filter(chama=chama, account_type='income',    is_active=True)
        expense_accounts   = Account.objects.filter(chama=chama, account_type='expense',   is_active=True)

        def make_rows(accounts):
            rows = []
            for a in accounts:
                bal = a.balance(date_to=as_at)
                if bal != 0:
                    rows.append({'account': a, 'amount': bal})
            return rows

        asset_rows     = make_rows(asset_accounts)
        liability_rows = make_rows(liability_accounts)
        equity_rows    = make_rows(equity_accounts)

        # Current period net profit (year-to-date up to as_at)
        year_start = date(date.fromisoformat(as_at).year, 1, 1).isoformat()
        net_profit = (
            sum(a.balance(year_start, as_at) for a in income_accounts) -
            sum(a.balance(year_start, as_at) for a in expense_accounts)
        )

        total_assets      = sum(r['amount'] for r in asset_rows)
        total_liabilities = sum(r['amount'] for r in liability_rows)
        total_equity      = sum(r['amount'] for r in equity_rows) + net_profit
        total_l_e         = total_liabilities + total_equity

        return render(request, 'ledger/balance_sheet.html', {
            'asset_rows': asset_rows,
            'liability_rows': liability_rows,
            'equity_rows': equity_rows,
            'net_profit': net_profit,
            'total_assets': total_assets,
            'total_liabilities': total_liabilities,
            'total_equity': total_equity,
            'total_l_e': total_l_e,
            'balanced': abs(total_assets - total_l_e) < Decimal('0.01'),
            'as_at': as_at,
        })
