from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.db.models import Sum
import csv
from members.models import Member
from contributions.models import Contribution
from loans.models import Loan
from payments.models import Payment
from tenants.scoping import scope, scope_members


class IncomeReportView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/income_report.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        r = self.request
        members = scope_members(r)
        contribs = scope(r, Contribution.objects.filter(is_voided=False))
        loans = scope(r, Loan.objects.all())
        from accounting.models import OtherIncome
        other_income = scope(r, OtherIncome.objects.filter(is_voided=False))

        ctx['total_reg_fees']      = members.aggregate(t=Sum('registration_fee'))['t'] or 0
        ctx['total_contributions'] = contribs.aggregate(t=Sum('amount'))['t'] or 0
        ctx['total_loans_given']   = loans.aggregate(t=Sum('loan_amount'))['t'] or 0
        ctx['total_interest']      = loans.aggregate(t=Sum('interest_amount'))['t'] or 0
        ctx['total_other_income']  = other_income.aggregate(t=Sum('amount'))['t'] or 0
        ctx['other_income_records'] = other_income.order_by('-date')

        # Investment returns
        from investments.models import InvestmentTransaction
        inv_return_types = [
            InvestmentTransaction.TYPE_INCOME,
            InvestmentTransaction.TYPE_DIVIDEND,
            InvestmentTransaction.TYPE_EXIT,
        ]
        inv_qs = scope(r, InvestmentTransaction.objects.filter(tx_type__in=inv_return_types))
        ctx['total_investment_returns'] = inv_qs.aggregate(t=Sum('amount'))['t'] or 0

        ctx['total_income'] = (
            ctx['total_reg_fees'] +
            ctx['total_contributions'] +
            ctx['total_interest'] +
            ctx['total_other_income'] +
            ctx['total_investment_returns']
        )
        return ctx


class ContributionReportView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/contribution_report.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['members'] = scope_members(self.request)
        ctx['contributions'] = scope(self.request, Contribution.objects.select_related('member').all())
        return ctx


class LoanReportView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/loan_report.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        loans = scope(self.request, Loan.objects.select_related('member').all())
        ctx['loans'] = loans
        ctx['total_issued'] = loans.aggregate(t=Sum('loan_amount'))['t'] or 0
        ctx['total_paid'] = loans.aggregate(t=Sum('amount_paid'))['t'] or 0
        ctx['total_balance'] = sum(l.balance for l in loans)
        return ctx


class MemberStatementView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/member_statement.html'

    def _get_member_data(self, member_id):
        from loans.models import LoanGuarantor
        member = scope_members(self.request).get(pk=member_id)
        return {
            'member': member,
            'contributions': member.contribution_set.filter(is_voided=False).order_by('-date'),
            'loans': member.loan_set.order_by('-date_taken'),
            'payments': member.payment_set.filter(is_voided=False).order_by('-date'),
            'penalties': member.penalties.filter(is_voided=False).order_by('-created_at'),
            'guarantees': LoanGuarantor.objects.filter(
                guarantor=member).select_related('loan__member'),
            'profit_share': member.profit_share(),
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        member_id = self.request.GET.get('member')
        ctx['members'] = scope_members(self.request)
        if member_id:
            try:
                data = self._get_member_data(member_id)
                ctx['selected_member'] = data['member']
                ctx.update(data)
            except Member.DoesNotExist:
                pass
        return ctx


class MemberStatementPrintView(LoginRequiredMixin, TemplateView):
    template_name = 'reports/member_statement_print.html'

    def get(self, request, pk):
        from loans.models import LoanGuarantor
        from django.shortcuts import render
        from django.http import Http404
        try:
            member = scope_members(request).get(pk=pk)
        except Member.DoesNotExist:
            raise Http404
        context = {
            'member': member,
            'contributions': member.contribution_set.filter(is_voided=False).order_by('-date'),
            'loans': member.loan_set.order_by('-date_taken'),
            'payments': member.payment_set.filter(is_voided=False).order_by('-date'),
            'penalties': member.penalties.filter(is_voided=False).order_by('-created_at'),
            'guarantees': LoanGuarantor.objects.filter(
                guarantor=member).select_related('loan__member'),
            'profit_share': member.profit_share(),
        }
        return render(request, self.template_name, context)


class MemberStatementCSVView(LoginRequiredMixin, TemplateView):
    def get(self, request, pk):
        from loans.models import LoanGuarantor
        from django.http import Http404
        import io, zipfile
        from django.utils.text import slugify
        try:
            member = scope_members(request).get(pk=pk)
        except Member.DoesNotExist:
            raise Http404

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            def make_csv(headers, rows):
                out = io.StringIO()
                w = csv.writer(out)
                w.writerow(headers)
                for row in rows:
                    w.writerow(row)
                return out.getvalue().encode('utf-8')

            zf.writestr('contributions.csv', make_csv(
                ['Month', 'Year', 'Amount', 'Date', 'Status'],
                [[c.get_month_display(), c.year, c.amount, c.date,
                  'Voided' if c.is_voided else 'Valid']
                 for c in member.contribution_set.order_by('-date')]
            ))
            zf.writestr('loans.csv', make_csv(
                ['Date Taken', 'Amount', 'Interest', 'Total Payable', 'Amount Paid', 'Balance', 'Due Date', 'Status'],
                [[l.date_taken, l.loan_amount, l.interest_amount, l.total_payable,
                  l.amount_paid, l.balance, l.due_date or '', l.get_status_display()]
                 for l in member.loan_set.order_by('-date_taken')]
            ))
            zf.writestr('payments.csv', make_csv(
                ['Date', 'Loan Amount', 'Payment', 'Notes', 'Status'],
                [[p.date, p.loan.loan_amount, p.amount, p.notes or '',
                  'Voided' if p.is_voided else 'Valid']
                 for p in member.payment_set.order_by('-date')]
            ))
            zf.writestr('penalties.csv', make_csv(
                ['Meeting', 'Date', 'Reason', 'Amount', 'Paid'],
                [[p.meeting.title, p.meeting.date, p.get_reason_display(),
                  p.amount, 'Yes' if p.paid else 'No']
                 for p in member.penalties.filter(is_voided=False).order_by('-created_at')]
            ))
            zf.writestr('guarantees.csv', make_csv(
                ['Borrower', 'Loan Amount', 'Amount Guaranteed', 'Loan Balance', 'Loan Status'],
                [[g.loan.member.name, g.loan.loan_amount, g.amount_guaranteed,
                  g.loan.balance, g.loan.get_status_display()]
                 for g in LoanGuarantor.objects.filter(guarantor=member).select_related('loan__member')]
            ))
            ps = member.profit_share()
            zf.writestr('summary.csv', make_csv(
                ['Item', 'Amount'],
                [
                    ['Total Contributions', member.total_contributions()],
                    ['Total Loans', member.total_loans()],
                    ['Loan Balance', member.total_loan_balance()],
                    ['Unpaid Penalties', member.unpaid_penalties()],
                    ['Profit Share (%)', ps['member_share_pct']],
                    ['Profit Share (KES)', ps['member_profit']],
                ]
            ))

        buf.seek(0)
        filename = f"statement_{slugify(member.name)}.zip"
        response = HttpResponse(buf.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class ExportContributionsCSV(LoginRequiredMixin, TemplateView):
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contributions.csv"'
        w = csv.writer(response)
        w.writerow(['Member', 'Amount', 'Month', 'Year', 'Date'])
        for c in scope(request, Contribution.objects.select_related('member').all()):
            w.writerow([c.member.name, c.amount, c.get_month_display(), c.year, c.date])
        return response


class ExportLoansCSV(LoginRequiredMixin, TemplateView):
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="loans.csv"'
        w = csv.writer(response)
        w.writerow(['Member', 'Loan Amount', 'Duration', 'Interest', 'Total Payable',
                    'Amount Paid', 'Balance', 'Status', 'Date Taken', 'Due Date'])
        for l in scope(request, Loan.objects.select_related('member').all()):
            w.writerow([l.member.name, l.loan_amount, l.duration_months, l.interest_amount,
                        l.total_payable, l.amount_paid, l.balance, l.get_status_display(),
                        l.date_taken, l.due_date])
        return response


class ExportPaymentsCSV(LoginRequiredMixin, TemplateView):
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="payments.csv"'
        w = csv.writer(response)
        w.writerow(['Member', 'Loan Amount', 'Payment Amount', 'Date', 'Notes'])
        for p in scope(request, Payment.objects.select_related('member', 'loan').all()):
            w.writerow([p.member.name, p.loan.loan_amount, p.amount, p.date, p.notes])
        return response


class ExportMembersCSV(LoginRequiredMixin, TemplateView):
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="members.csv"'
        w = csv.writer(response)
        w.writerow(['Name', 'Phone', 'Registration Fee', 'Date Joined',
                    'Total Contributions', 'Total Loans', 'Loan Balance'])
        for m in scope_members(request):
            w.writerow([m.name, m.phone, m.registration_fee, m.date_joined,
                        m.total_contributions(), m.total_loans(), m.total_loan_balance()])
        return response
