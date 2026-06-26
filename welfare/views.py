from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.db.models import Sum
from decimal import Decimal
from datetime import date

from .models import WelfareClaim, WelfareContribution, WelfareSettings
from .forms import (
    WelfareClaimForm, WelfareContributionForm, WelfareSettingsForm,
    ClaimApprovalForm, ClaimDisbursementForm, ClaimRejectionForm,
    BulkWelfareContributionForm,
)
from members.models import Member


def _get_claim(request, pk, **extra):
    chama = getattr(request, 'chama', None)
    if chama:
        return get_object_or_404(WelfareClaim, pk=pk, chama=chama, **extra)
    return get_object_or_404(WelfareClaim, pk=pk, **extra)


def _get_welfare_contrib(request, pk):
    chama = getattr(request, 'chama', None)
    if chama:
        return get_object_or_404(WelfareContribution, pk=pk, member__chama=chama)
    return get_object_or_404(WelfareContribution, pk=pk)


def _treasurer(user):
    p = getattr(user, 'profile', None)
    if not p or p.role not in ('admin', 'treasurer'):
        raise PermissionDenied


def _admin(user):
    p = getattr(user, 'profile', None)
    if not p or p.role != 'admin':
        raise PermissionDenied


# ── Dashboard ────────────────────────────────────────────────────────────────

class WelfareDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        from tenants.scoping import scope
        chama = getattr(request, 'chama', None)
        total_in = scope(request, WelfareContribution.objects.filter(
            is_voided=False)).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        total_out = scope(request, WelfareClaim.objects.filter(
            status='disbursed')).aggregate(t=Sum('amount_disbursed'))['t'] or Decimal('0')
        total_committed = scope(request, WelfareClaim.objects.filter(
            status='approved')).aggregate(t=Sum('amount_approved'))['t'] or Decimal('0')
        balance = total_in - total_out

        recent_claims = scope(request, WelfareClaim.objects.select_related('member').order_by('-date_filed'))[:8]
        recent_contributions = scope(request, WelfareContribution.objects.filter(
            is_voided=False).select_related('member').order_by('-date'))[:8]

        pending_count = scope(request, WelfareClaim.objects.filter(status='pending')).count()
        approved_count = scope(request, WelfareClaim.objects.filter(status='approved')).count()

        return render(request, 'welfare/dashboard.html', {
            'total_in': total_in,
            'total_out': total_out,
            'total_committed': total_committed,
            'balance': balance,
            'available_balance': balance - total_committed,
            'recent_claims': recent_claims,
            'recent_contributions': recent_contributions,
            'pending_count': pending_count,
            'approved_count': approved_count,
            'settings': WelfareSettings.get(chama=chama),
        })


# ── Claims ───────────────────────────────────────────────────────────────────

class ClaimListView(LoginRequiredMixin, View):
    def get(self, request):
        from tenants.scoping import scope
        qs = scope(request, WelfareClaim.objects.select_related('member').order_by('-date_filed'))
        status = request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        return render(request, 'welfare/claim_list.html', {
            'claims': qs,
            'filter_status': status,
            'status_choices': WelfareClaim.STATUS_CHOICES,
            'pending_count': scope(request, WelfareClaim.objects.filter(status='pending')).count(),
        })


class ClaimDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        claim = _get_claim(request, pk)
        contributions = claim.contributions.filter(is_voided=False)
        total_raised = contributions.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        return render(request, 'welfare/claim_detail.html', {
            'claim': claim,
            'contributions': contributions,
            'total_raised': total_raised,
            'approval_form': ClaimApprovalForm(initial={'amount_approved': claim.amount_requested}),
            'disbursement_form': ClaimDisbursementForm(
                initial={'amount_disbursed': claim.amount_approved}),
            'rejection_form': ClaimRejectionForm(),
        })


class ClaimCreateView(LoginRequiredMixin, View):
    def get(self, request):
        _treasurer(request.user)
        form = WelfareClaimForm(chama=getattr(request, 'chama', None))
        return render(request, 'welfare/claim_form.html', {'form': form, 'title': 'File New Claim'})

    def post(self, request):
        _treasurer(request.user)
        form = WelfareClaimForm(request.POST, request.FILES, chama=getattr(request, 'chama', None))
        if form.is_valid():
            claim = form.save(commit=False)
            claim.chama = getattr(request, 'chama', None)
            claim.save()
            _notify_claim(claim, 'filed')
            messages.success(request, f"Claim #{claim.pk} filed for {claim.member.name}.")
            return redirect('welfare:claim_detail', pk=claim.pk)
        return render(request, 'welfare/claim_form.html', {'form': form, 'title': 'File New Claim'})


class ClaimEditView(LoginRequiredMixin, View):
    """Edit a pending claim — only allowed before approval."""
    def get(self, request, pk):
        _treasurer(request.user)
        claim = _get_claim(request, pk)
        if claim.status != WelfareClaim.STATUS_PENDING:
            messages.error(request, "Only pending claims can be edited.")
            return redirect('welfare:claim_detail', pk=pk)
        form = WelfareClaimForm(instance=claim, chama=getattr(request, 'chama', None))
        return render(request, 'welfare/claim_form.html', {'form': form, 'title': f'Edit Claim #{pk}', 'claim': claim})

    def post(self, request, pk):
        _treasurer(request.user)
        claim = _get_claim(request, pk)
        if claim.status != WelfareClaim.STATUS_PENDING:
            messages.error(request, "Only pending claims can be edited.")
            return redirect('welfare:claim_detail', pk=pk)
        form = WelfareClaimForm(request.POST, request.FILES, instance=claim, chama=getattr(request, 'chama', None))
        if form.is_valid():
            form.save()
            messages.success(request, f"Claim #{pk} updated.")
            return redirect('welfare:claim_detail', pk=pk)
        return render(request, 'welfare/claim_form.html', {'form': form, 'title': f'Edit Claim #{pk}', 'claim': claim})


class ClaimApproveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _treasurer(request.user)
        claim = _get_claim(request, pk, status=WelfareClaim.STATUS_PENDING)
        form = ClaimApprovalForm(request.POST)
        if form.is_valid():
            claim.status = WelfareClaim.STATUS_APPROVED
            claim.amount_approved = form.cleaned_data['amount_approved']
            claim.date_approved = date.today()
            claim.reviewed_by = request.user
            claim.notes = (claim.notes + '\n' + form.cleaned_data.get('notes', '')).strip()
            claim.save()
            _notify_claim(claim, 'approved')
            messages.success(request, f"Claim #{claim.pk} approved for KES {claim.amount_approved:,.2f}.")
        return redirect('welfare:claim_detail', pk=pk)


class ClaimDisburseView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _treasurer(request.user)
        claim = _get_claim(request, pk, status=WelfareClaim.STATUS_APPROVED)
        form = ClaimDisbursementForm(request.POST)
        if form.is_valid():
            from tenants.scoping import scope
            amount = form.cleaned_data['amount_disbursed']
            # Fund sufficiency check
            total_in = scope(request, WelfareContribution.objects.filter(
                is_voided=False)).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            total_out = scope(request, WelfareClaim.objects.filter(
                status='disbursed')).aggregate(t=Sum('amount_disbursed'))['t'] or Decimal('0')
            available = total_in - total_out
            if amount > available:
                messages.error(
                    request,
                    f"Insufficient funds. Available balance: KES {available:,.2f}. "
                    f"Requested: KES {amount:,.2f}."
                )
                return redirect('welfare:claim_detail', pk=pk)
            claim.status = WelfareClaim.STATUS_DISBURSED
            claim.amount_disbursed = amount
            claim.date_disbursed = date.today()
            claim.disbursement_method = form.cleaned_data['disbursement_method']
            claim.disbursement_ref = form.cleaned_data['disbursement_ref']
            claim.disbursed_by = request.user
            claim.save()
            _notify_claim(claim, 'disbursed')
            messages.success(request, f"KES {claim.amount_disbursed:,.2f} disbursed for Claim #{claim.pk}.")
        return redirect('welfare:claim_detail', pk=pk)


class ClaimRejectView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _treasurer(request.user)
        claim = _get_claim(request, pk, status=WelfareClaim.STATUS_PENDING)
        form = ClaimRejectionForm(request.POST)
        if form.is_valid():
            claim.status = WelfareClaim.STATUS_REJECTED
            claim.rejection_reason = form.cleaned_data['rejection_reason']
            claim.reviewed_by = request.user
            claim.date_approved = date.today()
            claim.save()
            _notify_claim(claim, 'rejected')
            messages.warning(request, f"Claim #{claim.pk} rejected.")
        return redirect('welfare:claim_detail', pk=pk)


# ── Contributions ────────────────────────────────────────────────────────────

class ContributionListView(LoginRequiredMixin, View):
    def get(self, request):
        from tenants.scoping import scope
        qs = scope(request, WelfareContribution.objects.select_related('member', 'claim').order_by('-date'))
        q = request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(member__name__icontains=q)
        total = qs.filter(is_voided=False).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        return render(request, 'welfare/contribution_list.html', {
            'contributions': qs,
            'total': total,
            'q': q,
        })


class ContributionCreateView(LoginRequiredMixin, View):
    def get(self, request):
        _treasurer(request.user)
        chama = getattr(request, 'chama', None)
        settings = WelfareSettings.get(chama=chama)
        claim_id = request.GET.get('claim')
        initial_amount = settings.standard_contribution
        # Use per-type rate if a specific claim is pre-selected
        if claim_id:
            try:
                claim = WelfareClaim.objects.get(pk=claim_id)
                initial_amount = settings.rate_for(claim.claim_type)
            except WelfareClaim.DoesNotExist:
                pass
        form = WelfareContributionForm(initial={
            'amount': initial_amount,
            'date': date.today(),
        }, chama=chama)
        if claim_id:
            form.initial['claim'] = claim_id
        return render(request, 'welfare/contribution_form.html', {'form': form})

    def post(self, request):
        _treasurer(request.user)
        form = WelfareContributionForm(request.POST, chama=getattr(request, 'chama', None))
        if form.is_valid():
            contrib = form.save(commit=False)
            contrib.created_by = request.user
            contrib.save()
            messages.success(request, f"Welfare contribution of KES {contrib.amount:,.2f} recorded.")
            return redirect('welfare:contribution_list')
        return render(request, 'welfare/contribution_form.html', {'form': form})


class ContributionVoidView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _admin(request.user)
        contrib = _get_welfare_contrib(request, pk)
        reason = request.POST.get('reason', '').strip() or 'Voided by admin'
        contrib.is_voided = True
        contrib.void_reason = reason
        contrib.save()
        messages.success(request, "Welfare contribution voided.")
        return redirect('welfare:contribution_list')


class BulkContributionView(LoginRequiredMixin, View):
    """Raise a welfare contribution from ALL active members for a specific claim."""
    def get(self, request):
        _treasurer(request.user)
        chama = getattr(request, 'chama', None)
        settings = WelfareSettings.get(chama=chama)
        # Pre-select claim if passed
        initial = {'amount': settings.standard_contribution, 'date': date.today()}
        claim_id = request.GET.get('claim')
        if claim_id:
            initial['claim'] = claim_id
        from tenants.scoping import scope
        form = BulkWelfareContributionForm(initial=initial, chama=chama)
        return render(request, 'welfare/bulk_contribution.html', {'form': form})

    def post(self, request):
        _treasurer(request.user)
        chama = getattr(request, 'chama', None)
        form = BulkWelfareContributionForm(request.POST, chama=chama)
        if form.is_valid():
            claim = form.cleaned_data['claim']
            amount = form.cleaned_data['amount']
            pay_date = form.cleaned_data['date']
            method = form.cleaned_data['payment_method']
            from tenants.scoping import scope_members
            members = scope_members(request).filter(status='active')
            count = 0
            for member in members:
                WelfareContribution.objects.create(
                    member=member,
                    amount=amount,
                    date=pay_date,
                    payment_method=method,
                    claim=claim,
                    created_by=request.user,
                )
                count += 1
            messages.success(request, f"{count} welfare contributions recorded for Claim #{claim.pk}.")
            return redirect('welfare:claim_detail', pk=claim.pk)
        return render(request, 'welfare/bulk_contribution.html', {'form': form})


# ── Settings ─────────────────────────────────────────────────────────────────

class WelfareSettingsView(LoginRequiredMixin, View):
    def get(self, request):
        _admin(request.user)
        chama = getattr(request, 'chama', None)
        settings_obj = WelfareSettings.get(chama=chama)
        form = WelfareSettingsForm(instance=settings_obj)
        return render(request, 'welfare/settings.html', {
            'form': form,
            'rate_summary': _rate_summary(settings_obj),
        })

    def post(self, request):
        _admin(request.user)
        chama = getattr(request, 'chama', None)
        form = WelfareSettingsForm(request.POST, instance=WelfareSettings.get(chama=chama))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.chama = chama
            obj.save()
            messages.success(request, "Welfare settings updated.")
            return redirect('welfare:dashboard')
        return render(request, 'welfare/settings.html', {
            'form': form,
            'rate_summary': _rate_summary(WelfareSettings.get(chama=chama)),
        })


def _rate_summary(settings_obj):
    """Returns list of (label, effective_rate, is_specific) for display."""
    items = [
        ('Hospitalisation',      settings_obj.rate_hospital,   'hospital'),
        ('Funeral / Bereavement', settings_obj.rate_funeral,   'funeral'),
        ('Maternity',            settings_obj.rate_maternity,   'maternity'),
        ('Disability',           settings_obj.rate_disability,  'disability'),
        ('Other',                settings_obj.rate_other,       'other'),
    ]
    result = []
    for label, specific_rate, _ in items:
        if specific_rate:
            result.append((label, specific_rate, True))
        else:
            result.append((label, settings_obj.standard_contribution, False))
    return result


# ── Export ───────────────────────────────────────────────────────────────────

class ClaimListPrintView(LoginRequiredMixin, View):
    def get(self, request):
        from tenants.scoping import scope
        qs = scope(request, WelfareClaim.objects.select_related('member').order_by('-date_filed'))
        status = request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        total = qs.aggregate(t=Sum('amount_disbursed'))['t'] or Decimal('0')
        return render(request, 'welfare/claim_list_print.html', {'claims': qs, 'total': total})


class ClaimListCSVView(LoginRequiredMixin, View):
    def get(self, request):
        from core.exports import csv_response
        from tenants.scoping import scope
        qs = scope(request, WelfareClaim.objects.select_related('member').order_by('-date_filed'))
        headers = ['#', 'Member', 'Type', 'Beneficiary', 'Relation', 'Requested',
                   'Approved', 'Disbursed', 'Status', 'Date Filed', 'Date Disbursed']
        rows = [[
            c.pk, c.member.name, c.get_claim_type_display(), c.beneficiary,
            c.beneficiary_relation or 'Self',
            c.amount_requested, c.amount_approved or '', c.amount_disbursed or '',
            c.get_status_display(), c.date_filed, c.date_disbursed or '',
        ] for c in qs]
        return csv_response('welfare_claims.csv', headers, rows)


# ── Notification helper ───────────────────────────────────────────────────────

def _notify_claim(claim, action):
    pass  # notifications removed
