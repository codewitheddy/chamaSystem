from django.urls import path
from .views import (
    LoanListView, LoanCreateView, LoanUpdateView,
    LoanDeleteView, LoanDetailView, LoanCalculatorView,
    CollateralCreateView, CollateralDeleteView,
    GuarantorAddView, GuarantorDeleteView, GuarantorsReportView,
    MemberContributionCheckView,
    EmergencyLoanListView, EmergencyLoanCreateView,
    LoanProductListView, LoanProductCreateView, LoanProductUpdateView,
    LoanProductDeleteView, LoanProductAjaxView,
    LoanSchedulePrintView, LoanScheduleCSVView,
    LoanListPrintView, LoanListCSVView,
)

app_name = 'loans'

urlpatterns = [
    path('', LoanListView.as_view(), name='list'),
    path('add/', LoanCreateView.as_view(), name='add'),
    path('<int:pk>/', LoanDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', LoanUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', LoanDeleteView.as_view(), name='delete'),
    path('calculator/', LoanCalculatorView.as_view(), name='calculator'),
    path('member-check/', MemberContributionCheckView.as_view(), name='member_check'),
    # Emergency loans
    path('emergency/', EmergencyLoanListView.as_view(), name='emergency_list'),
    path('emergency/add/', EmergencyLoanCreateView.as_view(), name='emergency_add'),
    # Collateral
    path('<int:loan_pk>/collateral/add/', CollateralCreateView.as_view(), name='collateral_add'),
    path('collateral/<int:pk>/delete/', CollateralDeleteView.as_view(), name='collateral_delete'),
    # Guarantors
    path('<int:loan_pk>/guarantor/add/', GuarantorAddView.as_view(), name='guarantor_add'),
    path('guarantor/<int:pk>/delete/', GuarantorDeleteView.as_view(), name='guarantor_delete'),
    path('guarantors/', GuarantorsReportView.as_view(), name='guarantors_report'),
    # Loan Products / Settings
    path('settings/', LoanProductListView.as_view(), name='product_list'),
    path('settings/add/', LoanProductCreateView.as_view(), name='product_add'),
    path('settings/<int:pk>/edit/', LoanProductUpdateView.as_view(), name='product_edit'),
    path('settings/<int:pk>/delete/', LoanProductDeleteView.as_view(), name='product_delete'),
    path('product-info/', LoanProductAjaxView.as_view(), name='product_info'),
    # Schedule export
    path('<int:pk>/schedule/print/', LoanSchedulePrintView.as_view(), name='schedule_print'),
    path('<int:pk>/schedule/csv/', LoanScheduleCSVView.as_view(), name='schedule_csv'),
    path('print/', LoanListPrintView.as_view(), name='list_print'),
    path('export/csv/', LoanListCSVView.as_view(), name='list_csv'),
]
