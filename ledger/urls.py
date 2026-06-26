from django.urls import path
from . import views

app_name = 'ledger'

urlpatterns = [
    path('cashbook/',      views.CashbookView.as_view(),       name='cashbook'),
    path('journal/',       views.JournalView.as_view(),        name='journal'),
    path('accounts/',      views.ChartOfAccountsView.as_view(), name='coa'),
    path('trial-balance/', views.TrialBalanceView.as_view(),   name='trial_balance'),
    path('profit-loss/',   views.ProfitLossView.as_view(),     name='profit_loss'),
    path('balance-sheet/', views.BalanceSheetView.as_view(),   name='balance_sheet'),
]
