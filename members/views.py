from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.views import View
from django.urls import reverse_lazy
from django.db import models
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404, render
from datetime import date
import csv
import io
from .models import Member
from .forms import MemberForm, MemberDeactivateForm, MemberExitForm
from accounts.mixins import TreasurerRequiredMixin, AdminRequiredMixin
from tenants.scoping import scope, scope_members


def _get_member(request, pk, **extra):
    """Fetch a member scoped to the current chama."""
    chama = getattr(request, 'chama', None)
    filters = {'pk': pk, **extra}
    if chama:
        filters['chama'] = chama
    return get_object_or_404(Member, **filters)


class MemberListView(LoginRequiredMixin, ListView):
    model = Member
    template_name = 'members/member_list.html'
    context_object_name = 'members'
    paginate_by = 20

    def get_queryset(self):
        qs = scope_members(self.request)
        q = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', 'active')
        sort = self.request.GET.get('sort', 'az')

        if status == 'disabled':
            qs = qs.filter(status=Member.STATUS_DISABLED)
        elif status == 'exited':
            qs = qs.filter(status=Member.STATUS_EXITED)
        elif status == 'all':
            pass
        else:
            qs = qs.filter(status=Member.STATUS_ACTIVE)

        if q:
            qs = qs.filter(models.Q(name__icontains=q) | models.Q(phone__icontains=q))

        if sort == 'za':
            qs = qs.order_by('-name')
        elif sort == 'newest':
            qs = qs.order_by('-date_joined', '-pk')
        elif sort == 'oldest':
            qs = qs.order_by('date_joined', 'pk')
        else:  # default a-z
            qs = qs.order_by('name')

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = scope_members(self.request)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['status'] = self.request.GET.get('status', 'active')
        ctx['sort'] = self.request.GET.get('sort', 'az')
        ctx['active_count'] = base.filter(status=Member.STATUS_ACTIVE).count()
        ctx['disabled_count'] = base.filter(status=Member.STATUS_DISABLED).count()
        ctx['exited_count'] = base.filter(status=Member.STATUS_EXITED).count()
        return ctx


class MemberCreateView(TreasurerRequiredMixin, SuccessMessageMixin, CreateView):
    model = Member
    form_class = MemberForm
    template_name = 'members/member_form.html'
    success_url = reverse_lazy('members:list')
    success_message = "Member added successfully."

    def form_valid(self, form):
        form.instance.chama = self.request.chama
        return super().form_valid(form)


class MemberUpdateView(TreasurerRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Member
    form_class = MemberForm
    template_name = 'members/member_form.html'
    success_message = "Member updated successfully."

    def get_queryset(self):
        return scope_members(self.request)

    def dispatch(self, request, *args, **kwargs):
        member = _get_member(request, kwargs['pk'])
        if member.status == Member.STATUS_EXITED:
            messages.error(request, "Exited members cannot be edited.")
            return redirect('members:detail', pk=member.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('members:detail', kwargs={'pk': self.object.pk})


class MemberDetailView(LoginRequiredMixin, DetailView):
    model = Member
    template_name = 'members/member_detail.html'
    context_object_name = 'member'

    def get_queryset(self):
        return scope_members(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['contributions'] = self.object.contribution_set.all()
        ctx['loans'] = self.object.loan_set.all()
        ctx['payments'] = self.object.payment_set.all()
        from loans.models import LoanGuarantor
        ctx['guarantees'] = LoanGuarantor.objects.filter(
            guarantor=self.object
        ).select_related('loan__member')
        return ctx


class MemberDeactivateView(TreasurerRequiredMixin, View):
    """Temporarily disable a member — reversible."""
    def get(self, request, pk):
        member = _get_member(request, pk)
        if member.status != Member.STATUS_ACTIVE:
            messages.warning(request, "Member is not currently active.")
            return redirect('members:detail', pk=pk)
        form = MemberDeactivateForm()
        return render(request, 'members/member_deactivate.html', {'member': member, 'form': form})

    def post(self, request, pk):
        member = _get_member(request, pk)
        form = MemberDeactivateForm(request.POST)
        if form.is_valid():
            member.status = Member.STATUS_DISABLED
            member.is_active = False
            member.deactivation_reason = form.cleaned_data.get('reason', '')
            member.save()
            messages.success(request, f"{member.name} has been disabled.")
            return redirect('members:detail', pk=pk)
        return render(request, 'members/member_deactivate.html', {'member': member, 'form': form})


class MemberActivateView(TreasurerRequiredMixin, View):
    def post(self, request, pk):
        member = _get_member(request, pk)
        member.status = Member.STATUS_ACTIVE
        member.is_active = True
        member.deactivation_reason = ''
        member.save()
        messages.success(request, f"{member.name} has been re-enabled.")
        return redirect('members:detail', pk=pk)


class MemberExitView(AdminRequiredMixin, View):
    """Full account closure with settlement summary."""
    template_name = 'members/member_exit.html'

    def dispatch(self, request, *args, **kwargs):
        member = _get_member(request, kwargs['pk'])
        if member.status == Member.STATUS_EXITED:
            messages.error(request, "This member has already exited.")
            return redirect('members:detail', pk=member.pk)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        member = _get_member(request, pk)
        summary = member.exit_summary()
        form = MemberExitForm()
        return render(request, self.template_name, {
            'member': member,
            'summary': summary,
            'form': form,
            'unpaid_penalties': member.penalties.filter(paid=False).select_related('meeting'),
        })

    def post(self, request, pk):
        member = _get_member(request, pk)
        form = MemberExitForm(request.POST)
        if form.is_valid():
            member.status = Member.STATUS_EXITED
            member.is_active = False
            member.exit_date = date.today()
            member.exit_notes = form.cleaned_data.get('notes', '')
            member.deactivation_reason = 'Exited'
            member.exit_settlement_amount = form.cleaned_data.get('settlement_amount')
            member.exit_settlement_method = form.cleaned_data.get('settlement_method', '')
            member.exit_settlement_ref    = form.cleaned_data.get('settlement_ref', '')
            member.save()

            # Close all outstanding loans — settlement covers the balance
            member.loan_set.filter(status__in=['active', 'late']).update(status='cleared')

            # Mark all unpaid penalties as paid — covered by settlement
            # Loop individually so amount_paid is set and the accounting signal fires
            for penalty in member.penalties.filter(paid=False, is_voided=False):
                penalty.paid = True
                penalty.amount_paid = penalty.amount
                penalty.paid_ref = f"exit-settlement:{member.pk}"
                penalty.save()

            # Post ledger entry for the settlement payout/collection
            settlement_amount = form.cleaned_data.get('settlement_amount')
            if settlement_amount and settlement_amount > 0:
                from accounting.models import Transaction
                summary = member.exit_summary()
                net = summary['net']
                direction = Transaction.DEBIT if net >= 0 else Transaction.CREDIT
                method_label = dict(form.SETTLEMENT_CHOICES).get(
                    form.cleaned_data.get('settlement_method', ''), ''
                )
                ref_part = form.cleaned_data.get('settlement_ref', '')
                Transaction.objects.create(
                    date=member.exit_date,
                    category=Transaction.CAT_OTHER,
                    direction=direction,
                    amount=settlement_amount,
                    description=f"Member exit settlement — {member.name}"
                                + (f" via {method_label}" if method_label else "")
                                + (f" ({ref_part})" if ref_part else ""),
                    member=member,
                    reference=f"exit:{member.pk}",
                    is_manual=True,
                )

            messages.success(
                request,
                f"{member.name}'s account has been closed. Exit recorded on {member.exit_date}."
            )
            return redirect('members:list')
        summary = member.exit_summary()
        return render(request, self.template_name, {
            'member': member,
            'summary': summary,
            'form': form,
            'unpaid_penalties': member.penalties.filter(paid=False).select_related('meeting'),
        })


class ExitedMemberStatementView(LoginRequiredMixin, View):
    """Read-only statement for an exited member — printable."""
    def get(self, request, pk):
        member = _get_member(request, pk, status=Member.STATUS_EXITED)
        summary = member.exit_summary()
        context = {
            'member': member,
            'summary': summary,
            'contributions': member.contribution_set.order_by('year', 'month'),
            'loans': member.loan_set.order_by('date_taken'),
            'payments': member.payment_set.order_by('date'),
            'penalties': member.penalties.order_by('meeting__date'),
        }
        return render(request, 'members/member_exited_statement.html', context)


class MemberDeleteView(AdminRequiredMixin, View):
    """Hard delete — only allowed if member has zero financial history and is not exited."""
    def get(self, request, pk):
        member = _get_member(request, pk)
        if member.status == Member.STATUS_EXITED:
            messages.error(request, "Exited members cannot be deleted. Their records are permanent.")
            return redirect('members:detail', pk=pk)
        has_loans = member.loan_set.exists()
        has_contributions = member.contribution_set.exists()
        can_delete = not has_loans and not has_contributions
        return render(request, 'members/member_confirm_delete.html', {
            'member': member,
            'has_loans': has_loans,
            'has_contributions': has_contributions,
            'can_delete': can_delete,
        })

    def post(self, request, pk):
        member = _get_member(request, pk)
        if member.status == Member.STATUS_EXITED:
            messages.error(request, "Exited members cannot be deleted.")
            return redirect('members:detail', pk=pk)
        if member.loan_set.exists() or member.contribution_set.exists():
            messages.error(request, "Cannot delete — use Exit to close the account instead.")
            return redirect('members:exit', pk=pk)
        name = member.name
        member.delete()
        messages.success(request, f"{name} has been permanently removed.")
        return redirect('members:list')


class MemberImportView(TreasurerRequiredMixin, TemplateView):
    template_name = 'members/member_import.html'

    def post(self, request, *args, **kwargs):
        csv_file = request.FILES.get('csv_file')
        if not csv_file or not csv_file.name.endswith('.csv'):
            messages.error(request, "Please upload a valid .csv file.")
            return redirect('members:import')

        decoded = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
        created, skipped, errors = 0, 0, []

        for i, row in enumerate(reader, start=2):
            name = row.get('name', '').strip()
            phone = row.get('phone', '').strip()
            reg_fee = row.get('registration_fee', '0').strip() or '0'
            if not name:
                errors.append(f"Row {i}: name is required.")
                continue
            if Member.objects.filter(phone=phone).exists():
                skipped += 1
                continue
            try:
                Member.objects.create(name=name, phone=phone, registration_fee=reg_fee,
                                      chama=request.chama)
                created += 1
            except Exception as e:
                errors.append(f"Row {i}: {e}")

        if created:
            messages.success(request, f"{created} member(s) imported successfully.")
        if skipped:
            messages.warning(request, f"{skipped} row(s) skipped (duplicate phone).")
        for err in errors:
            messages.error(request, err)

        return redirect('members:list')


class MemberListPrintView(LoginRequiredMixin, View):
    def get(self, request):
        status = request.GET.get('status', 'active')
        qs = scope_members(request)
        if status == 'active':
            qs = qs.filter(status=Member.STATUS_ACTIVE)
        elif status == 'disabled':
            qs = qs.filter(status=Member.STATUS_DISABLED)
        elif status == 'exited':
            qs = qs.filter(status=Member.STATUS_EXITED)
        labels = {'active': 'Active', 'disabled': 'Disabled', 'exited': 'Exited', 'all': 'All'}
        return render(request, 'members/member_list_print.html', {
            'members': qs,
            'status_label': labels.get(status, 'All'),
        })


class MemberListCSVView(LoginRequiredMixin, View):
    def get(self, request):
        from core.exports import csv_response
        status = request.GET.get('status', 'all')
        qs = scope_members(request)
        if status == 'active':
            qs = qs.filter(status=Member.STATUS_ACTIVE)
        elif status == 'disabled':
            qs = qs.filter(status=Member.STATUS_DISABLED)
        elif status == 'exited':
            qs = qs.filter(status=Member.STATUS_EXITED)
        headers = ['Name', 'Phone', 'Email', 'Reg. Fee', 'Date Joined', 'Status',
                   'Total Contributions', 'Loan Balance', 'Unpaid Penalties']
        rows = [[m.name, m.phone, m.email, m.registration_fee, m.date_joined,
                 m.get_status_display(), m.total_contributions(),
                 m.total_loan_balance(), m.unpaid_penalties()] for m in qs]
        return csv_response('members.csv', headers, rows)
