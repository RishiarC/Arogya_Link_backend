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

    def validate_priority(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Priority must be between 1 and 5.')
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return attrs

        existing_contacts = EmergencyContact.objects.filter(user=user)
        if self.instance:
            existing_contacts = existing_contacts.exclude(pk=self.instance.pk)

        if not self.instance and existing_contacts.count() >= 5:
            raise serializers.ValidationError('Only 5 emergency contacts can be saved.')

        priority = attrs.get('priority')
        if priority is None and not self.instance:
            priority = self._get_next_priority(existing_contacts)
            if priority is None:
                raise serializers.ValidationError('Only 5 emergency contacts can be saved.')
            attrs['priority'] = priority
        elif priority is None and self.instance:
            priority = self.instance.priority

        if existing_contacts.filter(priority=priority).exists():
            raise serializers.ValidationError(
                {'priority': 'This priority is already assigned to another emergency contact.'}
            )

        return attrs

    @staticmethod
    def _get_next_priority(existing_contacts):
        used_priorities = set(existing_contacts.values_list('priority', flat=True))
        for priority in range(1, 6):
            if priority not in used_priorities:
                return priority
        return None

class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = '__all__'
        read_only_fields = ('user',)
