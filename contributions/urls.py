from django.urls import path
from .views import (
    ContributionListView, ContributionCreateView, ContributionUpdateView,
    ContributionVoidView, ContributionDefaultersView, BulkContributionView,
    ContributionListPrintView, ContributionListCSVView,
)

app_name = 'contributions'

urlpatterns = [
    path('', ContributionListView.as_view(), name='list'),
    path('add/', ContributionCreateView.as_view(), name='add'),
    path('bulk/', BulkContributionView.as_view(), name='bulk'),
    path('print/', ContributionListPrintView.as_view(), name='list_print'),
    path('export/csv/', ContributionListCSVView.as_view(), name='list_csv'),
    path('<int:pk>/edit/', ContributionUpdateView.as_view(), name='edit'),
    path('<int:pk>/void/', ContributionVoidView.as_view(), name='void'),
    path('defaulters/', ContributionDefaultersView.as_view(), name='defaulters'),
]
