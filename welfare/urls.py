from django.urls import path
from . import views

app_name = 'welfare'

urlpatterns = [
    path('', views.WelfareDashboardView.as_view(), name='dashboard'),
    path('claims/', views.ClaimListView.as_view(), name='claim_list'),
    path('claims/add/', views.ClaimCreateView.as_view(), name='claim_add'),
    path('claims/<int:pk>/', views.ClaimDetailView.as_view(), name='claim_detail'),
    path('claims/<int:pk>/edit/', views.ClaimEditView.as_view(), name='claim_edit'),
    path('claims/<int:pk>/approve/', views.ClaimApproveView.as_view(), name='claim_approve'),
    path('claims/<int:pk>/disburse/', views.ClaimDisburseView.as_view(), name='claim_disburse'),
    path('claims/<int:pk>/reject/', views.ClaimRejectView.as_view(), name='claim_reject'),
    path('claims/print/', views.ClaimListPrintView.as_view(), name='claim_list_print'),
    path('claims/export/csv/', views.ClaimListCSVView.as_view(), name='claim_list_csv'),
    path('contributions/', views.ContributionListView.as_view(), name='contribution_list'),
    path('contributions/add/', views.ContributionCreateView.as_view(), name='contribution_add'),
    path('contributions/bulk/', views.BulkContributionView.as_view(), name='bulk_contribution'),
    path('contributions/<int:pk>/void/', views.ContributionVoidView.as_view(), name='contribution_void'),
    path('settings/', views.WelfareSettingsView.as_view(), name='settings'),
]
