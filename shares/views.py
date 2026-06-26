from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, DetailView, CreateView, TemplateView, UpdateView
from django.views import View
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Sum

from .models import ShareAccount, ShareTransaction, ShareConfig
from .forms import SharePurchaseForm, ShareAdjustmentForm, ShareConfigForm
from members.models import Member
from accounts.mixins import AdminRequiredMixin, TreasurerRequiredMixin


class ShareDashboardView(TreasurerRequiredMixin, TemplateView):
    template_name = 'shares/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from tenants.scoping import scope
        chama = getattr(self.request, 'chama', None)
        config = ShareConfig.get(chama=chama)
        accounts = scope(self.request, ShareAccount.objects.select_related('member')).order_by('-shares_held')
        total_shares = accounts.aggregate(t=Sum('shares_held'))['t'] or 0
        ctx.update({
            'config': config,
            'accounts': accounts,
            'total_shares': total_shares,
            'total_capital': total_shares * config.par_value,
            'member_count': accounts.count(),
        })
        return ctx


class MemberShareAccountView(LoginRequiredMixin, DetailView):
    model = ShareAccount
    template_name = 'shares/member_account.html'
    context_object_name = 'account'

    def get_object(self):
        from tenants.scoping import scope_members
        member = get_object_or_404(scope_members(self.request), pk=self.kwargs['member_pk'])
        acct, _ = ShareAccount.objects.get_or_create(member=member)
        return acct

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        chama = self.object.member.chama if self.object.member else None
        ctx['config'] = ShareConfig.get(chama=chama)
        ctx['transactions'] = self.object.transactions.all()[:50]
        return ctx


class SharePurchaseView(TreasurerRequiredMixin, SuccessMessageMixin, CreateView):
    model = ShareTransaction
    form_class = SharePurchaseForm
    template_name = 'shares/purchase.html'
    success_message = "Share purchase recorded."

    def get_member(self):
        from tenants.scoping import scope_members
        return get_object_or_404(scope_members(self.request), pk=self.kwargs['member_pk'])

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw['member'] = self.get_member()
        return kw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['member'] = self.get_member()
        ctx['config'] = ShareConfig.get(chama=getattr(self.request, 'chama', None))
        return ctx

    def form_valid(self, form):
        member = self.get_member()
        acct, _ = ShareAccount.objects.get_or_create(member=member)
        form.instance.account = acct
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('shares:member_account', kwargs={'member_pk': self.kwargs['member_pk']})


class ShareAdjustmentView(AdminRequiredMixin, SuccessMessageMixin, CreateView):
    """Admin-only: post any share transaction type (transfer, refund, bonus, adjustment)."""
    model = ShareTransaction
    form_class = ShareAdjustmentForm
    template_name = 'shares/adjustment.html'
    success_message = "Share transaction recorded."

    def get_member(self):
        from tenants.scoping import scope_members
        return get_object_or_404(scope_members(self.request), pk=self.kwargs['member_pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['member'] = self.get_member()
        return ctx

    def form_valid(self, form):
        member = self.get_member()
        acct, _ = ShareAccount.objects.get_or_create(member=member)
        form.instance.account = acct
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('shares:member_account', kwargs={'member_pk': self.kwargs['member_pk']})


class ShareConfigView(AdminRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ShareConfig
    form_class = ShareConfigForm
    template_name = 'shares/config.html'
    success_url = reverse_lazy('shares:dashboard')
    success_message = "Share configuration updated."

    def get_object(self):
        chama = getattr(self.request, 'chama', None)
        return ShareConfig.get(chama=chama)
