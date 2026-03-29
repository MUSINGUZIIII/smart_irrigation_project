from rest_framework import serializers
from .models import SensorData, Threshold


class SensorDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorData
        fields = ['timestamp', 'soil_moisture', 'temperature', 'humidity']


class ThresholdSerializer(serializers.ModelSerializer):
    class Meta:
        model = Threshold
        fields = ['soil_moisture']

