from django.urls import path
from . import views

app_name = 'tenants'

urlpatterns = [
    # Public
    path('', views.LandingView.as_view(), name='landing'),
    path('register/', views.ChamaSignupView.as_view(), name='signup'),
    # Super-admin (staff only)
    path('superadmin/', views.SuperAdminDashboardView.as_view(), name='dashboard'),
    path('superadmin/add/', views.ChamaCreateView.as_view(), name='add'),
    path('superadmin/<int:pk>/edit/', views.ChamaUpdateView.as_view(), name='edit'),
    path('superadmin/<int:pk>/toggle/', views.ChamaToggleView.as_view(), name='toggle'),
    path('superadmin/<int:pk>/plan/', views.ChamaPlanView.as_view(), name='plan'),
    path('superadmin/payments/<int:pk>/verify/', views.PaymentVerifyView.as_view(), name='payment_verify'),
    path('superadmin/<int:pk>/reset-password/', views.ChamaResetPasswordView.as_view(), name='reset_password'),
    # Chama self-service subscription
    path('subscription/', views.SubscriptionView.as_view(), name='subscription'),
    path('subscription/submit/', views.SubscriptionPaymentSubmitView.as_view(), name='subscription_submit'),
]
