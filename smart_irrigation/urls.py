from django.urls import path, include
from django.contrib import admin
from accounts.views import home
from irrigation import views as irrigation_views
from irrigation import api
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('irrigation/', include('irrigation.urls')),  # Irrigation app URLs
    path('accounts/', include('accounts.urls')),
    path('about/', irrigation_views.about, name='about'),
    path('contact/', irrigation_views.contact, name='contact'),
    path('help/', irrigation_views.help, name='help'),
    path('__debug__/', include('debug_toolbar.urls')),
    path('keep-alive/', irrigation_views.keep_alive, name='keep-alive'),
    path('water-usage/', irrigation_views.water_usage, name='water-usage'),

    # API URLs
    path('api/sensor_data/', api.receive_sensor_data, name='receive_sensor_data'),
    path('api/control/', api.control_system, name='control_system'),
    path('api/status/', api.get_system_status, name='get_system_status'),
    path('api/save_config/', api.save_configuration, name='save_configuration'),
    path('api/get_config/', api.get_configuration, name='get_configuration'),
    path('api/watering_history/', api.watering_history, name='watering_history'),
    path('api/add-note/', api.add_note, name='add-note'),
    path('api/schedule/', api.schedule_irrigation, name='schedule-irrigation'),
    path('api/device-heartbeat/', api.device_heartbeat, name='device-heartbeat'),
    path('api/schedule/', api.schedule_list, name='schedule-list'),
    path('api/schedule/<int:pk>/', api.schedule_detail, name='schedule-detail'),
    path('api/water-usage/', api.receive_water_usage, name='receive-water-usage'),
    path('api/water-usage/history/', api.get_water_usage_history, name='water-usage-history'),
    path('api/tank-level/', api.get_current_tank_level, name='current-tank-level'),

    path('api/irrigation-frequency/', api.get_irrigation_frequency, name='api-irrigation-frequency'),
    path('api/water-stock-alert/', api.get_water_stock_alert, name='water-stock-alert'),
    path('api/record-irrigation/', api.record_irrigation_event, name='record-irrigation'),
    path('api/irrigation-predictions/', api.get_irrigation_predictions, name='irrigation-predictions'),


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# Only serve media files in development, not in production
if settings.DEBUG and not settings.IS_PRODUCTION:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
