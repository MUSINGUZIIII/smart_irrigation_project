from django.urls import path, include
from . import views
from .views import EnvCheckView, trigger_notifications

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('control-panel/', views.control_panel, name='control-panel'),
    path('download-manual-confirm/', views.download_user_manual_confirm, name='download_user_manual_confirm'),
    path('send-support-message/', views.send_support_message, name='send_support_message'),
    path('download-manual/', views.download_user_manual, name='download_user_manual'),
    path('visualize/', views.visualize_data, name='visualize-data'),
    path('get-sensor-data/', views.get_sensor_data, name='get-sensor-data'),
    path('download-data/', views.download_data, name='download-data'),
    path('env-check/', EnvCheckView.as_view(), name='env_check'),
    path('cron/notifications/', trigger_notifications, name='trigger_notifications'),
    path('manifest.webmanifest', views.manifest_view, name='manifest'),
    path('favicon.ico', views.favicon_view, name='favicon'),
    path('irrigation-frequency/', views.irrigation_frequency, name='irrigation-frequency'),
    path('download-report/', views.download_irrigation_report, name='download-report'),
]
