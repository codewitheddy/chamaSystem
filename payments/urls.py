from django.urls import path
from .views import PaymentListView, PaymentCreateView, PaymentVoidView, PaymentListPrintView, PaymentListCSVView

app_name = 'payments'

urlpatterns = [
    path('', PaymentListView.as_view(), name='list'),
    path('add/', PaymentCreateView.as_view(), name='add'),
    path('print/', PaymentListPrintView.as_view(), name='list_print'),
    path('export/csv/', PaymentListCSVView.as_view(), name='list_csv'),
    path('<int:pk>/void/', PaymentVoidView.as_view(), name='void'),
    path('<int:pk>/delete/', PaymentVoidView.as_view(), name='delete'),
]
