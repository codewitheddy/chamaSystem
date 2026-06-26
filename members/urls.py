from django.urls import path
from .views import (
    MemberListView, MemberCreateView, MemberUpdateView,
    MemberDeleteView, MemberDetailView, MemberImportView,
    MemberDeactivateView, MemberActivateView, MemberExitView,
    ExitedMemberStatementView, MemberListPrintView, MemberListCSVView,
)

app_name = 'members'

urlpatterns = [
    path('', MemberListView.as_view(), name='list'),
    path('add/', MemberCreateView.as_view(), name='add'),
    path('import/', MemberImportView.as_view(), name='import'),
    path('print/', MemberListPrintView.as_view(), name='list_print'),
    path('export/csv/', MemberListCSVView.as_view(), name='list_csv'),
    path('<int:pk>/', MemberDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', MemberUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', MemberDeleteView.as_view(), name='delete'),
    path('<int:pk>/disable/', MemberDeactivateView.as_view(), name='disable'),
    path('<int:pk>/enable/', MemberActivateView.as_view(), name='enable'),
    path('<int:pk>/exit/', MemberExitView.as_view(), name='exit'),
    path('<int:pk>/statement/', ExitedMemberStatementView.as_view(), name='exited_statement'),
]
