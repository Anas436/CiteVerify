from django.urls import path
from . import views

app_name = 'detector'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('new/', views.new_analysis, name='new_analysis'),
    path('<uuid:analysis_id>/progress/', views.analysis_progress, name='analysis_progress'),
    path('<uuid:analysis_id>/status/', views.analysis_status_api, name='analysis_status_api'),
    path('<uuid:analysis_id>/results/', views.analysis_results, name='analysis_results'),
    path('<uuid:analysis_id>/report/', views.report_detail, name='report_detail'),
    path('history/', views.analysis_history, name='history'),
    path('<uuid:analysis_id>/delete/', views.delete_analysis, name='delete_analysis'),
]
