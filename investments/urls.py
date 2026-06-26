from django.urls import path
from . import views

app_name = 'investments'

urlpatterns = [
    path('', views.InvestmentDashboardView.as_view(), name='dashboard'),
    path('list/', views.InvestmentListView.as_view(), name='list'),
    path('add/', views.InvestmentCreateView.as_view(), name='add'),
    path('<int:pk>/', views.InvestmentDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.InvestmentUpdateView.as_view(), name='edit'),
    path('<int:pk>/transactions/add/', views.TransactionAddView.as_view(), name='tx_add'),
    path('transactions/<int:pk>/delete/', views.TransactionDeleteView.as_view(), name='tx_delete'),
    path('<int:pk>/documents/upload/', views.DocumentUploadView.as_view(), name='doc_upload'),
    path('documents/<int:pk>/delete/', views.DocumentDeleteView.as_view(), name='doc_delete'),
    path('print/', views.InvestmentListPrintView.as_view(), name='list_print'),
    path('export/csv/', views.InvestmentListCSVView.as_view(), name='list_csv'),
]
