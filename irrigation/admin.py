from django.contrib import admin
from .models import SensorData, ControlCommand

admin.site.register(SensorData)
admin.site.register(ControlCommand)
