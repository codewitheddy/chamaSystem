from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

_admin_url = getattr(settings, 'ADMIN_URL', 'admin').strip('/')

urlpatterns = [
    path('', include('tenants.urls')),   # landing + signup at root
    path(f'{_admin_url}/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('members/', include('members.urls')),
    path('contributions/', include('contributions.urls')),
    path('loans/', include('loans.urls')),
    path('payments/', include('payments.urls')),
    path('reports/', include('reports.urls')),
    path('meetings/', include('meetings.urls')),
    path('accounting/', include('accounting.urls')),
    path('shares/', include('shares.urls')),
    path('welfare/', include('welfare.urls')),
    path('investments/', include('investments.urls')),
    path('agm/', include('agm.urls')),
    path('board/', include('board.urls')),
    path('ledger/', include('ledger.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
