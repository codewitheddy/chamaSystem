from django.urls import path
from .views import (
    UserLoginView, UserLogoutView, UserListView, UserCreateView,
    UserUpdateRoleView, UserToggleActiveView, UserResetPasswordView,
    MemberPortalLoginView, MemberPortalView,
    CreateMemberPortalAccountView,
)

app_name = 'accounts'

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('users/', UserListView.as_view(), name='users'),
    path('users/add/', UserCreateView.as_view(), name='user_add'),
    path('users/<int:pk>/role/', UserUpdateRoleView.as_view(), name='user_role'),
    path('users/<int:pk>/toggle/', UserToggleActiveView.as_view(), name='user_toggle'),
    path('users/<int:pk>/reset-password/', UserResetPasswordView.as_view(), name='user_reset_password'),
    # Member portal
    path('member/login/', MemberPortalLoginView.as_view(), name='member_login'),
    path('member/portal/', MemberPortalView.as_view(), name='member_portal'),
    path('member/create/<int:member_id>/', CreateMemberPortalAccountView.as_view(), name='create_portal_account'),
]
