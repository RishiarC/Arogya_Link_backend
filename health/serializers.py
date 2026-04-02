from rest_framework import serializers
from .models import MedicalReport, SmartwatchData, HealthHistory, EmergencyContact, Reminder

class MedicalReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalReport
        fields = '__all__'
        read_only_fields = ('user',)

class SmartwatchDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SmartwatchData
        fields = '__all__'
        read_only_fields = ('user',)

class HealthHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthHistory
        fields = '__all__'
        read_only_fields = ('user',)

class EmergencyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyContact
        fields = '__all__'
        read_only_fields = ('user', )

class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = '__all__'
        read_only_fields = ('user',)
