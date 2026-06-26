import re
from django.http import Http404
from django.shortcuts import render
from django.conf import settings
from .models import Chama

# Paths that are always accessible regardless of subscription status
_ALWAYS_ALLOWED = (
    '/accounts/login/',
    '/accounts/logout/',
    '/accounts/member/login/',
    '/register/',
    '/superadmin/',
    '/subscription/',   # allow expired groups to reach the payment page
    '/static/',
    '/media/',
)


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.chama = self._resolve(request)

        if request.user.is_authenticated:
            # Staff/superusers must only access the superadmin panel.
            # If they land on any chama-scoped URL, redirect them out.
            if request.user.is_staff and request.chama:
                # Allow static/media through; redirect everything else
                if not any(request.path.startswith(p) for p in ('/static/', '/media/')):
                    from django.shortcuts import redirect
                    return redirect('/superadmin/')

            # Subscription enforcement — only for non-staff users
            elif (
                not request.user.is_staff
                and request.chama
                and not any(request.path.startswith(p) for p in _ALWAYS_ALLOWED)
            ):
                status = request.chama.subscription_status
                if status in ('trial_expired', 'expired'):
                    return render(request, 'tenants/subscription_expired.html', {
                        'chama': request.chama,
                        'status': status,
                    }, status=402)

        return self.get_response(request)

    def _resolve(self, request):
        host = request.META.get('HTTP_HOST', '').lower().split(':')[0]

        # Always-public paths — no chama needed
        public_paths = ('/register/', '/superadmin/')
        if any(request.path.startswith(p) for p in public_paths):
            return None

        # IP addresses (127.0.0.1) — no subdomain concept
        if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', host):
            return self._dev_fallback(request)

        # Determine the root domain from BASE_DOMAIN setting, stripping any port
        base_domain = settings.BASE_DOMAIN.split(':')[0].lower()

        # Check if the host is exactly the root domain (with or without www)
        if host == base_domain or host == f'www.{base_domain}':
            if settings.DEBUG:
                return self._dev_fallback(request)
            return None

        # Check if host ends with .base_domain — meaning it has a subdomain prefix
        if host.endswith(f'.{base_domain}'):
            subdomain = host[: -(len(base_domain) + 1)]
        else:
            # Fallback: treat first part as subdomain only for plain domains (e.g. localhost)
            parts = host.split('.')
            has_subdomain = len(parts) >= 2 and parts[0] not in ('', 'www')
            subdomain = parts[0] if has_subdomain else ''

        if not subdomain:
            if settings.DEBUG:
                return self._dev_fallback(request)
            return None

        try:
            return Chama.objects.get(slug=subdomain, is_active=True)
        except Chama.DoesNotExist:
            if settings.DEBUG:
                try:
                    return Chama.objects.get(slug=subdomain)
                except Chama.DoesNotExist:
                    pass
            raise Http404(f"No active chama found for '{subdomain}'")

    def _dev_fallback(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not user.is_staff:
            try:
                profile = user.profile
                if profile.chama and profile.chama.is_active:
                    return profile.chama
            except Exception:
                pass
        if user and user.is_authenticated and user.is_staff:
            return None
        return Chama.objects.filter(is_active=True).order_by('created_at').first()
