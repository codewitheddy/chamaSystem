from django.urls import path
from . import views

app_name = 'shares'

urlpatterns = [
    path('', views.ShareDashboardView.as_view(), name='dashboard'),
    path('config/', views.ShareConfigView.as_view(), name='config'),
    path('member/<int:member_pk>/', views.MemberShareAccountView.as_view(), name='member_account'),
    path('member/<int:member_pk>/purchase/', views.SharePurchaseView.as_view(), name='purchase'),
    path('member/<int:member_pk>/adjust/', views.ShareAdjustmentView.as_view(), name='adjust'),
]
