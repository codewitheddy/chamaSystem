"""
TenantMixin — attach to any view to automatically scope querysets to request.chama.

Usage in a view:
    class MyView(TenantMixin, LoginRequiredMixin, ListView):
        model = Member
        # get_queryset() automatically filters by chama

Or use the helper directly:
    qs = Member.objects.for_chama(request.chama)
"""
from django.core.exceptions import ImproperlyConfigured


class TenantMixin:
    """
    Mixin for class-based views.
    Provides self.chama and scopes get_queryset() to the current tenant.
    """

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.chama = getattr(request, 'chama', None)

    def get_queryset(self):
        qs = super().get_queryset()
        if self.chama is None:
            return qs
        # Only filter if the model has a chama field
        if hasattr(qs.model, 'chama_id'):
            return qs.filter(chama=self.chama)
        return qs


def chama_required(view_func):
    """Decorator for function-based views — raises 404 if no chama on request."""
    from django.http import Http404
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'chama', None):
            raise Http404("No chama context.")
        return view_func(request, *args, **kwargs)
    return wrapper
