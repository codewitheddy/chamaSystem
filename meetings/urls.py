from django.urls import path
from .views import (
    MeetingListView, MeetingCreateView, MeetingUpdateView,
    MeetingDeleteView, MeetingDetailView,
    MinutesUpdateView, AttendanceView,
    PenaltyAddView, PenaltyDeleteView, PenaltyTogglePaidView, PenaltyPayView,
    PenaltyListView, PenaltyListPrintView, PenaltyListCSVView,
)

app_name = 'meetings'

urlpatterns = [
    path('', MeetingListView.as_view(), name='list'),
    path('add/', MeetingCreateView.as_view(), name='add'),
    path('<int:pk>/', MeetingDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', MeetingUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', MeetingDeleteView.as_view(), name='delete'),
    path('<int:pk>/minutes/', MinutesUpdateView.as_view(), name='minutes'),
    path('<int:pk>/attendance/', AttendanceView.as_view(), name='attendance'),
    path('<int:pk>/penalties/add/', PenaltyAddView.as_view(), name='penalty_add'),
    path('penalties/', PenaltyListView.as_view(), name='penalty_list'),
    path('penalties/print/', PenaltyListPrintView.as_view(), name='penalty_list_print'),
    path('penalties/export/csv/', PenaltyListCSVView.as_view(), name='penalty_list_csv'),
    path('penalties/<int:penalty_pk>/delete/', PenaltyDeleteView.as_view(), name='penalty_delete'),
    path('penalties/<int:penalty_pk>/toggle/', PenaltyTogglePaidView.as_view(), name='penalty_toggle'),
    path('penalties/<int:penalty_pk>/pay/', PenaltyPayView.as_view(), name='penalty_pay'),
]
