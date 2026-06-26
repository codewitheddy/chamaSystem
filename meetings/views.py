from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.views import View
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Meeting, Attendance, MeetingPenalty
from .forms import MeetingForm, MinutesForm, AttendanceForm, PenaltyForm
from members.models import Member
from accounts.mixins import TreasurerRequiredMixin, AdminRequiredMixin
from tenants.scoping import scope, scope_members


def _get_meeting(request, pk):
    chama = getattr(request, 'chama', None)
    if chama:
        return get_object_or_404(Meeting, pk=pk, chama=chama)
    return get_object_or_404(Meeting, pk=pk)


def _get_penalty(request, pk):
    chama = getattr(request, 'chama', None)
    if chama:
        return get_object_or_404(MeetingPenalty, pk=pk, meeting__chama=chama)
    return get_object_or_404(MeetingPenalty, pk=pk)


class MeetingListView(LoginRequiredMixin, ListView):
    model = Meeting
    template_name = 'meetings/meeting_list.html'
    context_object_name = 'meetings'
    paginate_by = 20

    def get_queryset(self):
        qs = scope(self.request, Meeting.objects.all())
        status = self.request.GET.get('status', '')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = scope(self.request, Meeting.objects.all())
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['scheduled_count'] = base.filter(status='scheduled').count()
        ctx['completed_count'] = base.filter(status='completed').count()
        return ctx


class MeetingCreateView(TreasurerRequiredMixin, SuccessMessageMixin, CreateView):
    model = Meeting
    form_class = MeetingForm
    template_name = 'meetings/meeting_form.html'
    success_url = reverse_lazy('meetings:list')
    success_message = "Meeting scheduled."

    def form_valid(self, form):
        form.instance.chama = self.request.chama
        return super().form_valid(form)


class MeetingUpdateView(TreasurerRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Meeting
    form_class = MeetingForm
    template_name = 'meetings/meeting_form.html'
    success_message = "Meeting updated."

    def dispatch(self, request, *args, **kwargs):
        meeting = _get_meeting(request, kwargs['pk'])
        if meeting.status == 'completed':
            messages.error(request, "Completed meetings cannot be edited. Change the status first if needed.")
            return redirect('meetings:detail', pk=meeting.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('meetings:detail', kwargs={'pk': self.object.pk})


class MeetingDeleteView(AdminRequiredMixin, DeleteView):
    model = Meeting
    template_name = 'meetings/meeting_confirm_delete.html'
    success_url = reverse_lazy('meetings:list')

    def get_queryset(self):
        return scope(self.request, Meeting.objects.all())


class MeetingDetailView(LoginRequiredMixin, DetailView):
    model = Meeting
    template_name = 'meetings/meeting_detail.html'
    context_object_name = 'meeting'

    def get_queryset(self):
        return scope(self.request, Meeting.objects.all())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['attendances'] = self.object.attendances.select_related('member').order_by('member__name')
        ctx['all_members'] = scope_members(self.request).exclude(status=Member.STATUS_EXITED)
        penalties = list(self.object.penalties.filter(is_voided=False).select_related('member'))
        ctx['penalties'] = penalties
        ctx['penalty_form'] = PenaltyForm(chama=getattr(self.request, 'chama', None))
        ctx['penalty_total'] = sum(p.amount for p in penalties)
        ctx['penalty_paid'] = sum(p.amount_paid or p.amount for p in penalties if p.paid)
        return ctx


class MinutesUpdateView(TreasurerRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Meeting
    form_class = MinutesForm
    template_name = 'meetings/minutes_form.html'
    success_message = "Minutes saved."

    def get_success_url(self):
        return reverse_lazy('meetings:detail', kwargs={'pk': self.object.pk})


class AttendanceView(TreasurerRequiredMixin, View):
    template_name = 'meetings/attendance_form.html'

    def get_meeting(self):
        return _get_meeting(self.request, self.kwargs['pk'])

    def get(self, request, pk):
        meeting = self.get_meeting()
        if meeting.status == 'completed':
            messages.error(request, "Attendance cannot be modified for a completed meeting.")
            return redirect('meetings:detail', pk=pk)
        members = scope_members(request).exclude(status=Member.STATUS_EXITED)
        existing = {a.member_id: a for a in meeting.attendances.all()}
        return self._render(request, meeting, members, existing)

    def post(self, request, pk):
        meeting = self.get_meeting()
        if meeting.status == 'completed':
            messages.error(request, "Attendance cannot be modified for a completed meeting.")
            return redirect('meetings:detail', pk=pk)
        members = scope_members(request).exclude(status=Member.STATUS_EXITED)
        # Save attendance for each member
        for member in members:
            present = f'present_{member.pk}' in request.POST
            notes = request.POST.get(f'notes_{member.pk}', '').strip()
            Attendance.objects.update_or_create(
                meeting=meeting, member=member,
                defaults={'present': present, 'notes': notes}
            )
        messages.success(request, "Attendance saved.")
        return redirect('meetings:detail', pk=meeting.pk)

    def _render(self, request, meeting, members, existing):
        from django.shortcuts import render
        rows = []
        for m in members:
            att = existing.get(m.pk)
            rows.append({
                'member': m,
                'present': att.present if att else False,
                'notes': att.notes if att else '',
            })
        return render(request, self.template_name, {
            'meeting': meeting,
            'rows': rows,
        })


class PenaltyAddView(TreasurerRequiredMixin, View):
    def post(self, request, pk):
        meeting = _get_meeting(request, pk)
        if meeting.status == 'completed':
            messages.error(request, "Cannot add penalties to a completed meeting.")
            return redirect('meetings:detail', pk=pk)
        form = PenaltyForm(request.POST, chama=getattr(request, 'chama', None))
        if form.is_valid():
            penalty = form.save(commit=False)
            penalty.meeting = meeting
            penalty.save()
            messages.success(request, f"Penalty recorded for {penalty.member.name}.")
        else:
            messages.error(request, "Invalid penalty data. Please check the form.")
        return redirect('meetings:detail', pk=pk)


class PenaltyDeleteView(TreasurerRequiredMixin, View):
    def post(self, request, penalty_pk):
        penalty = _get_penalty(request, penalty_pk)
        meeting_pk = penalty.meeting_id
        if penalty.meeting.status == 'completed':
            messages.error(request, "Cannot void penalties from a completed meeting.")
            return redirect('meetings:detail', pk=meeting_pk)
        if penalty.paid:
            messages.error(request, "Cannot void a paid penalty. Reverse the payment first.")
            return redirect('meetings:detail', pk=meeting_pk)
        reason = request.POST.get('void_reason', '').strip() or 'Voided'
        penalty.is_voided = True
        penalty.void_reason = reason
        penalty.save()
        messages.success(request, "Penalty voided.")
        return redirect('meetings:detail', pk=meeting_pk)


class PenaltyTogglePaidView(TreasurerRequiredMixin, View):
    """Only used to reverse a paid penalty back to unpaid."""
    def post(self, request, penalty_pk):
        penalty = _get_penalty(request, penalty_pk)
        if penalty.meeting.status == 'completed' and not penalty.paid:
            messages.error(request, "Use the Pay button to record payment.")
            return redirect('meetings:detail', pk=penalty.meeting_id)
        penalty.paid = not penalty.paid
        if not penalty.paid:
            penalty.amount_paid = None
            penalty.paid_ref = ''
        penalty.save()
        return redirect('meetings:detail', pk=penalty.meeting_id)


class PenaltyPayView(TreasurerRequiredMixin, View):
    """Record actual payment for a penalty — captures amount and reference."""
    def post(self, request, penalty_pk):
        from decimal import Decimal, InvalidOperation
        penalty = _get_penalty(request, penalty_pk)
        if penalty.paid:
            messages.warning(request, "Penalty is already marked as paid.")
            return redirect('meetings:detail', pk=penalty.meeting_id)
        raw_amount = request.POST.get('amount_paid', '').strip()
        paid_ref = request.POST.get('paid_ref', '').strip()
        try:
            amount_paid = Decimal(raw_amount)
            if amount_paid <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            messages.error(request, "Enter a valid payment amount.")
            return redirect('meetings:detail', pk=penalty.meeting_id)
        penalty.paid = True
        penalty.amount_paid = amount_paid
        penalty.paid_ref = paid_ref
        penalty.save()
        messages.success(request, f"Penalty payment of KES {amount_paid} recorded for {penalty.member.name}.")
        return redirect('meetings:detail', pk=penalty.meeting_id)


class PenaltyListView(LoginRequiredMixin, ListView):
    model = MeetingPenalty
    template_name = 'meetings/penalty_list.html'
    context_object_name = 'penalties'
    paginate_by = 30

    def get_queryset(self):
        qs = scope(self.request, MeetingPenalty.objects.select_related('member', 'meeting')).order_by('-meeting__date', '-created_at')
        member = self.request.GET.get('member', '')
        reason = self.request.GET.get('reason', '')
        paid = self.request.GET.get('paid', '')
        if member: qs = qs.filter(member_id=member)
        if reason: qs = qs.filter(reason=reason)
        if paid == '1': qs = qs.filter(paid=True)
        elif paid == '0': qs = qs.filter(paid=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_penalties = scope(self.request, MeetingPenalty.objects.all())
        ctx['total_amount'] = sum(p.amount for p in all_penalties)
        ctx['paid_amount'] = sum(p.amount for p in all_penalties.filter(paid=True))
        ctx['unpaid_amount'] = sum(p.amount for p in all_penalties.filter(paid=False))
        ctx['total_count'] = all_penalties.count()
        ctx['members'] = scope_members(self.request)
        ctx['reason_choices'] = MeetingPenalty.REASON_CHOICES
        ctx['filter_member'] = self.request.GET.get('member', '')
        ctx['filter_reason'] = self.request.GET.get('reason', '')
        ctx['filter_paid'] = self.request.GET.get('paid', '')
        return ctx


class PenaltyListPrintView(LoginRequiredMixin, View):
    def get(self, request):
        from django.shortcuts import render
        from django.db.models import Sum
        qs = scope(request, MeetingPenalty.objects.select_related('member', 'meeting').filter(is_voided=False)).order_by('-meeting__date')
        total_amount = qs.aggregate(t=Sum('amount'))['t'] or 0
        return render(request, 'meetings/penalty_list_print.html',
                      {'penalties': qs, 'total_amount': total_amount})


class PenaltyListCSVView(LoginRequiredMixin, View):
    def get(self, request):
        from core.exports import csv_response
        qs = scope(request, MeetingPenalty.objects.select_related('member', 'meeting')).order_by('-meeting__date')
        headers = ['Member', 'Meeting', 'Meeting Date', 'Reason', 'Description',
                   'Amount', 'Paid', 'Amount Paid', 'Reference']
        rows = [[
            p.member.name, p.meeting.title, p.meeting.date,
            p.get_reason_display(), p.description or '',
            p.amount, 'Yes' if p.paid else 'No',
            p.amount_paid or '', p.paid_ref or '',
        ] for p in qs]
        return csv_response('penalties.csv', headers, rows)
