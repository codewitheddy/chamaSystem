"""
Audit log middleware — records login, logout, and key write operations.
Logs go to the 'chama.audit' logger (→ logs/security.log in production).
"""
import logging
import time

logger = logging.getLogger('chama.audit')

# Paths that trigger an audit entry on POST (financial write operations)
_AUDIT_POST_PATHS = (
    '/contributions/',
    '/loans/',
    '/payments/',
    '/accounting/',
    '/welfare/',
    '/investments/',
    '/members/',
)


class AuditLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        elapsed = round((time.monotonic() - start) * 1000)

        user = getattr(request, 'user', None)
        username = user.username if user and user.is_authenticated else 'anonymous'
        ip = _get_ip(request)
        path = request.path
        method = request.method
        status = response.status_code

        # Always log auth events
        if path in ('/accounts/login/', '/accounts/member/login/'):
            if method == 'POST':
                if status in (302, 200) and user and user.is_authenticated:
                    logger.info('LOGIN_SUCCESS user=%s ip=%s', username, ip)
                elif status == 200:
                    # Form re-rendered = failed login
                    attempted = request.POST.get('username', '?')
                    logger.warning('LOGIN_FAILED username=%s ip=%s', attempted, ip)

        elif path == '/accounts/logout/' and method == 'POST':
            logger.info('LOGOUT user=%s ip=%s', username, ip)

        # Log financial write operations
        elif method == 'POST' and path.startswith(_AUDIT_POST_PATHS):
            if status in (302, 201):
                logger.info('WRITE user=%s ip=%s path=%s status=%s ms=%s',
                            username, ip, path, status, elapsed)

        return response


def _get_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '?')
