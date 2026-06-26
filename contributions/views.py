from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, CreateView, UpdateView, TemplateView
from django.views import View
from django.urls import reverse_lazy
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .models import Contribution
from .forms import ContributionForm, ContributionVoidForm
from members.models import Member
from accounts.mixins import TreasurerRequiredMixin, AdminRequiredMixin
from tenants.scoping import scope, scope_members
import datetime


class ContributionListView(LoginRequiredMixin, ListView):
    model = Contribution
    template_name = 'contributions/contribution_list.html'
    context_object_name = 'contributions'
    paginate_by = 20

    def get_queryset(self):
        qs = scope(self.request, Contribution.objects.select_related('member'))
        member_id = self.request.GET.get('member')
        q = self.request.GET.get('q', '').strip()
        if member_id:
            qs = qs.filter(member_id=member_id)
        if q:
            qs = qs.filter(member__name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.db.models import Sum, Count
        ctx['q'] = self.request.GET.get('q', '')

        # Full scope (unfiltered by search) for overall totals
        all_qs = scope(self.request, Contribution.objects.all())
        ctx['total_all'] = all_qs.filter(is_voided=False).aggregate(t=Sum('amount'))['t'] or 0
        ctx['count_all'] = all_qs.filter(is_voided=False).count()

        # Filtered queryset totals (matches current search)
        filtered_qs = self.get_queryset()
        ctx['total_filtered'] = filtered_qs.filter(is_voided=False).aggregate(t=Sum('amount'))['t'] or 0
        ctx['count_filtered'] = filtered_qs.filter(is_voided=False).count()
        ctx['count_voided'] = all_qs.filter(is_voided=True).count()

        # Unique contributing members
        ctx['contributing_members'] = all_qs.filter(
            is_voided=False).values('member').distinct().count()

        return ctx


class ContributionCreateView(TreasurerRequiredMixin, SuccessMessageMixin, CreateView):
    model = Contribution
    form_class = ContributionForm
    template_name = 'contributions/contribution_form.html'
    success_url = reverse_lazy('contributions:list')
    success_message = "Contribution recorded."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs

    def form_valid(self, form):
        member = form.cleaned_data.get('member')
        if member and member.status == Member.STATUS_EXITED:
            form.add_error('member', 'Cannot record a contribution for an exited member.')
            return self.form_invalid(form)
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ContributionUpdateView(TreasurerRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Contribution
    form_class = ContributionForm
    template_name = 'contributions/contribution_form.html'
    success_url = reverse_lazy('contributions:list')
    success_message = "Contribution updated."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['chama'] = getattr(self.request, 'chama', None)
        return kwargs


class ContributionVoidView(AdminRequiredMixin, View):
    def get(self, request, pk):
        contribution = get_object_or_404(Contribution, pk=pk)
        if contribution.is_voided:
            messages.warning(request, "This contribution is already voided.")
            return redirect('contributions:list')
        form = ContributionVoidForm()
        return render(request, 'contributions/contribution_void.html', {
            'contribution': contribution, 'form': form
        })

    def post(self, request, pk):
        contribution = get_object_or_404(Contribution, pk=pk)
        form = ContributionVoidForm(request.POST)
        if form.is_valid():
            from django.utils import timezone
            contribution.is_voided = True
            contribution.void_reason = form.cleaned_data['reason']
            contribution.voided_by = request.user
            contribution.voided_at = timezone.now()
            contribution.save()
            messages.success(request, "Contribution voided.")
            return redirect('contributions:list')
        return render(request, 'contributions/contribution_void.html', {
            'contribution': contribution, 'form': form
        })


class ContributionDefaultersView(LoginRequiredMixin, TemplateView):
    template_name = 'contributions/defaulters.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = datetime.date.today()
        month = int(self.request.GET.get('month', today.month))
        year = int(self.request.GET.get('year', today.year))

        paid_ids = scope(self.request, Contribution.objects.filter(
            month=month, year=year, is_voided=False
        )).values_list('member_id', flat=True)

        defaulters = scope_members(self.request).filter(
            status=Member.STATUS_ACTIVE
        ).exclude(id__in=paid_ids)
        ctx['defaulters'] = defaulters
        ctx['month'] = month
        ctx['year'] = year
        ctx['month_name'] = datetime.date(year, month, 1).strftime('%B')
        ctx['months'] = [{'num': i, 'name': datetime.date(year, i, 1).strftime('%B')} for i in range(1, 13)]
        ctx['years'] = range(today.year - 2, today.year + 1)
        return ctx


class BulkContributionView(TreasurerRequiredMixin, View):
    """Record contributions for all active members in one form submission."""
    template_name = 'contributions/bulk_contribution.html'

    def _get_context(self, month, year, post_data=None):
        import calendar as cal_module
        today = datetime.date.today()
        members = scope_members(self.request).filter(status=Member.STATUS_ACTIVE).order_by('name')
        paid_ids = set(scope(self.request, Contribution.objects.filter(
            month=month, year=year, is_voided=False
        )).values_list('member_id', flat=True))

        rows = []
        for m in members:
            already_paid = m.pk in paid_ids
            amount_val = post_data.get(f'amount_{m.pk}', '') if post_data else ''
            date_val = post_data.get(f'date_{m.pk}', str(today)) if post_data else str(today)
            rows.append({
                'member': m,
                'already_paid': already_paid,
                'amount': amount_val,
                'date': date_val,
            })

        return {
            'rows': rows,
            'month': month,
            'year': year,
            'month_name': datetime.date(year, month, 1).strftime('%B'),
            'months': [{'num': i, 'name': cal_module.month_name[i]} for i in range(1, 13)],
            'years': range(today.year - 2, today.year + 2),
            'today': today,
        }

    def get(self, request):
        today = datetime.date.today()
        month = int(request.GET.get('month', today.month))
        year = int(request.GET.get('year', today.year))
        return render(request, self.template_name, self._get_context(month, year))

    def post(self, request):
        today = datetime.date.today()
        month = int(request.POST.get('month', today.month))
        year = int(request.POST.get('year', today.year))

        members = scope_members(request).filter(status=Member.STATUS_ACTIVE)
        saved, skipped, errors = 0, 0, []

        for member in members:
            raw_amount = request.POST.get(f'amount_{member.pk}', '').strip()
            raw_date = request.POST.get(f'date_{member.pk}', '').strip()
            if not raw_amount:
                skipped += 1
                continue
            try:
                amount = float(raw_amount)
                if amount <= 0:
                    raise ValueError
            except ValueError:
                errors.append(f"{member.name}: invalid amount '{raw_amount}'")
                continue

            try:
                date = datetime.date.fromisoformat(raw_date) if raw_date else today
            except ValueError:
                date = today

            if scope(request, Contribution.objects.filter(member=member, month=month, year=year, is_voided=False)).exists():
                skipped += 1
                continue

            Contribution.objects.create(
                member=member,
                amount=amount,
                date=date,
                month=month,
                year=year,
                created_by=request.user,
            )
            saved += 1

        if saved:
            messages.success(request, f"{saved} contribution(s) recorded.")
        if skipped:
            messages.info(request, f"{skipped} member(s) skipped (blank or already paid).")
        for err in errors:
            messages.error(request, err)

        return redirect(f"{request.path}?month={month}&year={year}")


class ContributionListPrintView(LoginRequiredMixin, View):
    def get(self, request):
        from django.db.models import Sum
        qs = scope(request, Contribution.objects.select_related('member').order_by('-date'))
        q = request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(member__name__icontains=q)
        total = qs.filter(is_voided=False).aggregate(t=Sum('amount'))['t'] or 0
        return render(request, 'contributions/contribution_list_print.html',
                      {'contributions': qs, 'total': total})


class ContributionListCSVView(LoginRequiredMixin, View):
    def get(self, request):
        from core.exports import csv_response
        qs = scope(request, Contribution.objects.select_related('member').order_by('-date'))
        headers = ['Member', 'Amount', 'Month', 'Year', 'Date', 'Status', 'Void Reason',
                   'Created By', 'Voided By', 'Voided At']
        rows = [[
            c.member.name, c.amount, c.get_month_display(), c.year, c.date,
            'Voided' if c.is_voided else 'Valid',
            c.void_reason or '',
            c.created_by.username if c.created_by else '',
            c.voided_by.username if c.voided_by else '',
            c.voided_at.strftime('%Y-%m-%d %H:%M') if c.voided_at else '',
        ] for c in qs]
        return csv_response('contributions.csv', headers, rows)
