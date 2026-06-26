"""
Tenant scoping helpers.

Usage in views:
    from tenants.scoping import scope

    qs = scope(request, Member.objects.all())
    # → filters by member__chama or chama depending on the model
"""


def scope(request, qs):
    """
    Filter a queryset to the current chama.
    Detects whether the model has a direct 'chama' FK or goes via 'member__chama'
    or 'loan__member__chama' (e.g. LoanGuarantor).
    """
    chama = getattr(request, 'chama', None)
    if chama is None:
        return qs
    model = qs.model
    field_names = [f.name for f in model._meta.get_fields()]
    if 'chama' in field_names:
        return qs.filter(chama=chama)
    if 'member' in field_names:
        return qs.filter(member__chama=chama)
    if 'loan' in field_names:
        return qs.filter(loan__member__chama=chama)
    if 'account' in field_names:
        # ShareTransaction → account → member → chama
        return qs.filter(account__member__chama=chama)
    if 'investment' in field_names:
        # InvestmentTransaction → investment → chama
        return qs.filter(investment__chama=chama)
    return qs


def scope_members(request, qs=None):
    """Scope a Member queryset (or return a fresh scoped one)."""
    from members.models import Member
    if qs is None:
        qs = Member.objects.all()
    chama = getattr(request, 'chama', None)
    if chama:
        return qs.filter(chama=chama)
    return qs
