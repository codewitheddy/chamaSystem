from django.urls import path
from . import views

app_name = 'agm'

urlpatterns = [
    path('', views.AGMListView.as_view(), name='list'),
    path('add/', views.AGMCreateView.as_view(), name='add'),
    path('<int:pk>/', views.AGMDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.AGMUpdateView.as_view(), name='edit'),
    path('<int:pk>/status/', views.AGMStatusView.as_view(), name='status'),
    path('<int:pk>/minutes/', views.AGMMinutesView.as_view(), name='minutes'),
    path('<int:pk>/attendance/', views.AttendanceView.as_view(), name='attendance'),
    path('<int:pk>/agenda/add/', views.AgendaItemAddView.as_view(), name='agenda_add'),
    path('<int:pk>/resolutions/add/', views.ResolutionAddView.as_view(), name='resolution_add'),
    path('<int:pk>/print/', views.AGMPrintView.as_view(), name='print'),
    path('agenda/<int:item_pk>/done/', views.AgendaItemDoneView.as_view(), name='agenda_done'),
    path('agenda/<int:item_pk>/delete/', views.AgendaItemDeleteView.as_view(), name='agenda_delete'),
    path('resolutions/<int:res_pk>/status/', views.ResolutionStatusView.as_view(), name='resolution_status'),
    path('resolutions/<int:res_pk>/delete/', views.ResolutionDeleteView.as_view(), name='resolution_delete'),
    path('resolutions/<int:res_pk>/vote/', views.CastVoteView.as_view(), name='vote'),
    path('resolutions/<int:res_pk>/vote/admin/', views.AdminCastVoteView.as_view(), name='vote_admin'),
]
