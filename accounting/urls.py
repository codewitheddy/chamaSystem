from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.AccountingDashboardView.as_view(), name='dashboard'),
    path('ledger/', views.LedgerView.as_view(), name='ledger'),
    path('expenses/', views.ExpenseListView.as_view(), name='expenses'),
    path('expenses/add/', views.ExpenseCreateView.as_view(), name='expense_add'),
    path('expenses/<int:pk>/edit/', views.ExpenseUpdateView.as_view(), name='expense_edit'),
    path('expenses/<int:pk>/void/', views.ExpenseVoidView.as_view(), name='expense_void'),
    path('transactions/add/', views.ManualTransactionCreateView.as_view(), name='transaction_add'),
    path('transactions/<int:pk>/delete/', views.ManualTransactionDeleteView.as_view(), name='transaction_delete'),
    path('ledger/print/', views.LedgerPrintView.as_view(), name='ledger_print'),
    path('ledger/export/csv/', views.LedgerCSVView.as_view(), name='ledger_csv'),
    path('year-end/', views.YearEndPayoutListView.as_view(), name='year_end_list'),
    path('year-end/new/', views.YearEndPayoutCreateView.as_view(), name='year_end_create'),
    path('year-end/<int:pk>/', views.YearEndPayoutDetailView.as_view(), name='year_end_detail'),
    path('year-end/<int:pk>/mark-paid/<int:line_pk>/', views.YearEndLineMarkPaidView.as_view(), name='year_end_mark_paid'),
    path('other-income/', views.OtherIncomeListView.as_view(), name='other_income_list'),
    path('other-income/add/', views.OtherIncomeCreateView.as_view(), name='other_income_add'),
    path('other-income/<int:pk>/edit/', views.OtherIncomeUpdateView.as_view(), name='other_income_edit'),
    path('other-income/<int:pk>/void/', views.OtherIncomeVoidView.as_view(), name='other_income_void'),
]
