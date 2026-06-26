from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from datetime import date

from .models import AGM, AgendaItem, Resolution, Vote, AGMAttendance
from .forms import (AGMForm, AGMMinutesForm, AgendaItemForm,
                    ResolutionForm, VoteForm, BulkAttendanceForm)
from members.models import Member


def _get_agm(request, pk):
    from tenants.scoping import scope
    return get_object_or_404(scope(request, AGM.objects.all()), pk=pk)


def _get_member_scoped(request, pk):
    from tenants.scoping import scope_members
    return get_object_or_404(scope_members(request), pk=pk)


def _treasurer(user):
    p = getattr(user, 'profile', None)
    if not p or p.role not in ('admin', 'treasurer'):
        raise PermissionDenied


def _admin(user):
    p = getattr(user, 'profile', None)
    if not p or p.role != 'admin':
        raise PermissionDenied


# ── AGM List ─────────────────────────────────────────────────────────────────

class AGMListView(LoginRequiredMixin, View):
    def get(self, request):
        from tenants.scoping import scope
        from django.db.models import Count, Q
        chama = getattr(request, 'chama', None)
        agms = scope(request, AGM.objects.annotate(
            resolution_count=Count('resolutions', distinct=True),
            present_count=Count('attendances', filter=Q(attendances__present=True), distinct=True),
        ).order_by('-date'))
        from members.models import Member
        active_qs = Member.objects.filter(status='active')
        if chama:
            active_qs = active_qs.filter(chama=chama)
        return render(request, 'agm/agm_list.html', {
            'agms': agms,
            'active_member_count': active_qs.count(),
        })


# ── AGM Detail ───────────────────────────────────────────────────────────────

class AGMDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        agm = _get_agm(request, pk)
        # Check if current user's linked member has voted on each resolution
        member = _get_member(request.user)
        voted_ids = set()
        if member:
            voted_ids = set(
                Vote.objects.filter(member=member, resolution__agm=agm)
                .values_list('resolution_id', flat=True)
            )
        return render(request, 'agm/agm_detail.html', {
            'agm': agm,
            'agenda_items': agm.agenda_items.all(),
            'resolutions': agm.resolutions.all(),
            'attendances': agm.attendances.select_related('member').all(),
            'agenda_form': AgendaItemForm(initial={'order': agm.agenda_items.count() + 1}),
            'resolution_form': ResolutionForm(chama=getattr(request, 'chama', None)),
            'vote_form': VoteForm(),
            'voted_ids': voted_ids,
            'member': member,
            'minutes_form': AGMMinutesForm(instance=agm),
        })


# ── AGM CRUD ─────────────────────────────────────────────────────────────────

class AGMCreateView(LoginRequiredMixin, View):
    def get(self, request):
        _treasurer(request.user)
        form = AGMForm(initial={'year': date.today().year, 'date': date.today()})
        return render(request, 'agm/agm_form.html', {'form': form, 'title': 'Schedule AGM'})

    def post(self, request):
        _treasurer(request.user)
        form = AGMForm(request.POST)
        if form.is_valid():
            agm = form.save(commit=False)
            agm.status = AGM.STATUS_SCHEDULED
            agm.created_by = request.user
            agm.chama = getattr(request, 'chama', None)
            agm.save()
            messages.success(request, f"AGM '{agm.title}' scheduled.")
            return redirect('agm:detail', pk=agm.pk)
        return render(request, 'agm/agm_form.html', {'form': form, 'title': 'Schedule AGM'})


class AGMUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        _treasurer(request.user)
        agm = _get_agm(request, pk)
        form = AGMForm(instance=agm)
        return render(request, 'agm/agm_form.html', {'form': form, 'title': f'Edit — {agm.title}', 'agm': agm})

    def post(self, request, pk):
        _treasurer(request.user)
        agm = _get_agm(request, pk)
        form = AGMForm(request.POST, instance=agm)
        if form.is_valid():
            form.save()
            messages.success(request, "AGM updated.")
            return redirect('agm:detail', pk=pk)
        return render(request, 'agm/agm_form.html', {'form': form, 'title': f'Edit — {agm.title}', 'agm': agm})


class AGMStatusView(LoginRequiredMixin, View):
    """Open or close an AGM."""
    def post(self, request, pk):
        _treasurer(request.user)
        agm = _get_agm(request, pk)
        action = request.POST.get('action')
        if action == 'open' and agm.status == AGM.STATUS_SCHEDULED:
            agm.status = AGM.STATUS_OPEN
            agm.save()
            messages.success(request, "AGM is now open. Voting is live.")
        elif action == 'close' and agm.status == AGM.STATUS_OPEN:
            agm.status = AGM.STATUS_CLOSED
            agm.save()
            # Auto-finalise only resolutions that were actively voting
            for res in agm.resolutions.filter(status=Resolution.STATUS_VOTING):
                res.status = Resolution.STATUS_PASSED if res.passed else Resolution.STATUS_FAILED
                res.save()
            messages.success(request, "AGM closed. Resolutions finalised.")
        return redirect('agm:detail', pk=pk)


# ── Minutes ───────────────────────────────────────────────────────────────────

class AGMMinutesView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _treasurer(request.user)
        agm = _get_agm(request, pk)
        form = AGMMinutesForm(request.POST, instance=agm)
        if form.is_valid():
            form.save()
            messages.success(request, "Minutes saved.")
        return redirect('agm:detail', pk=pk)


# ── Agenda Items ──────────────────────────────────────────────────────────────

class AgendaItemAddView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _treasurer(request.user)
        agm = _get_agm(request, pk)
        form = AgendaItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.agm = agm
            item.save()
            messages.success(request, f"Agenda item '{item.title}' added.")
        else:
            messages.error(request, "Invalid agenda item.")
        return redirect('agm:detail', pk=pk)


class AgendaItemDoneView(LoginRequiredMixin, View):
    def post(self, request, item_pk):
        _treasurer(request.user)
        item = get_object_or_404(AgendaItem, pk=item_pk)
        item.is_done = not item.is_done
        notes = request.POST.get('notes', '').strip()
        if notes:
            item.notes = notes
        item.save()
        return redirect('agm:detail', pk=item.agm_id)


class AgendaItemDeleteView(LoginRequiredMixin, View):
    def post(self, request, item_pk):
        _admin(request.user)
        item = get_object_or_404(AgendaItem, pk=item_pk)
        agm_pk = item.agm_id
        item.delete()
        messages.success(request, "Agenda item removed.")
        return redirect('agm:detail', pk=agm_pk)


# ── Resolutions ───────────────────────────────────────────────────────────────

class ResolutionAddView(LoginRequiredMixin, View):
    def post(self, request, pk):
        _treasurer(request.user)
        agm = _get_agm(request, pk)
        form = ResolutionForm(request.POST, chama=getattr(request, 'chama', None))
        if form.is_valid():
            res = form.save(commit=False)
            res.agm = agm
            res.save()
            messages.success(request, f"Resolution '{res.title}' added.")
        else:
            messages.error(request, "Invalid resolution data.")
        return redirect('agm:detail', pk=pk)


class ResolutionStatusView(LoginRequiredMixin, View):
    """Open or close voting on a resolution."""
    def post(self, request, res_pk):
        _treasurer(request.user)
        res = get_object_or_404(Resolution, pk=res_pk)
        action = request.POST.get('action')
        if action == 'open_voting' and res.status == Resolution.STATUS_PENDING:
            res.status = Resolution.STATUS_VOTING
            res.save()
            messages.success(request, f"Voting opened for '{res.title}'.")
        elif action == 'close_voting' and res.status == Resolution.STATUS_VOTING:
            res.status = Resolution.STATUS_PASSED if res.passed else Resolution.STATUS_FAILED
            res.save()
            messages.success(request, f"Voting closed. Resolution {res.get_status_display()}.")
        elif action == 'withdraw':
            res.status = Resolution.STATUS_WITHDRAWN
            res.save()
            messages.warning(request, f"Resolution '{res.title}' withdrawn.")
        return redirect('agm:detail', pk=res.agm_id)


class ResolutionDeleteView(LoginRequiredMixin, View):
    def post(self, request, res_pk):
        _admin(request.user)
        res = get_object_or_404(Resolution, pk=res_pk)
        agm_pk = res.agm_id
        res.delete()
        messages.success(request, "Resolution deleted.")
        return redirect('agm:detail', pk=agm_pk)


# ── Voting ────────────────────────────────────────────────────────────────────

class CastVoteView(LoginRequiredMixin, View):
    def post(self, request, res_pk):
        res = get_object_or_404(Resolution, pk=res_pk, status=Resolution.STATUS_VOTING)
        if res.agm.status != AGM.STATUS_OPEN:
            messages.error(request, "Voting is not currently open.")
            return redirect('agm:detail', pk=res.agm_id)

        member = _get_member(request.user)
        if not member:
            messages.error(request, "No member account linked to your login.")
            return redirect('agm:detail', pk=res.agm_id)

        if Vote.objects.filter(resolution=res, member=member).exists():
            messages.warning(request, "You have already voted on this resolution.")
            return redirect('agm:detail', pk=res.agm_id)

        form = VoteForm(request.POST)
        if form.is_valid():
            Vote.objects.create(
                resolution=res,
                member=member,
                choice=form.cleaned_data['choice'],
            )
            messages.success(request, f"Vote cast: {form.cleaned_data['choice'].upper()}.")
        return redirect('agm:detail', pk=res.agm_id)


class AdminCastVoteView(LoginRequiredMixin, View):
    """Admin records a vote on behalf of a member (for in-person meetings)."""
    def post(self, request, res_pk):
        _treasurer(request.user)
        res = get_object_or_404(Resolution, pk=res_pk, status=Resolution.STATUS_VOTING)
        member_id = request.POST.get('member_id')
        choice = request.POST.get('choice')
        if not member_id or choice not in [Vote.YES, Vote.NO, Vote.ABSTAIN]:
            messages.error(request, "Invalid vote data.")
            return redirect('agm:detail', pk=res.agm_id)
        member = _get_member_scoped(request, member_id)
        Vote.objects.update_or_create(
            resolution=res, member=member,
            defaults={'choice': choice}
        )
        messages.success(request, f"Vote recorded for {member.name}.")
        return redirect('agm:detail', pk=res.agm_id)


# ── Attendance ────────────────────────────────────────────────────────────────

class AttendanceView(LoginRequiredMixin, View):
    def get(self, request, pk):
        _treasurer(request.user)
        agm = _get_agm(request, pk)
        from tenants.scoping import scope_members
        members = scope_members(request).filter(status='active').order_by('name')
        existing = {a.member_id: a for a in agm.attendances.all()}
        # Annotate each member with their attendance data for easy template access
        member_rows = []
        for m in members:
            att = existing.get(m.pk)
            member_rows.append({
                'member': m,
                'present': att.present if att else False,
                'proxy': att.represented_by if att else '',
            })
        return render(request, 'agm/attendance.html', {
            'agm': agm,
            'member_rows': member_rows,
        })

    def post(self, request, pk):
        _treasurer(request.user)
        agm = _get_agm(request, pk)
        from tenants.scoping import scope_members
        members = scope_members(request).filter(status='active')
        for member in members:
            present = f'present_{member.pk}' in request.POST
            proxy = request.POST.get(f'proxy_{member.pk}', '').strip()
            AGMAttendance.objects.update_or_create(
                agm=agm, member=member,
                defaults={'present': present, 'represented_by': proxy}
            )
        messages.success(request, "Attendance saved.")
        return redirect('agm:detail', pk=pk)


# ── Print ─────────────────────────────────────────────────────────────────────

class AGMPrintView(LoginRequiredMixin, View):
    def get(self, request, pk):
        agm = _get_agm(request, pk)
        return render(request, 'agm/agm_print.html', {
            'agm': agm,
            'agenda_items': agm.agenda_items.all(),
            'resolutions': agm.resolutions.all(),
            'attendances': agm.attendances.select_related('member').all(),
        })


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_member(user):
    """Return the Member linked to this user's account, if any."""
    try:
        profile = user.profile
        if profile.member:
            return profile.member
    except Exception:
        pass
    return None
