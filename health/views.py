from datetime import timedelta
from urllib.parse import quote

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from . import ml_utils
from .models import EmergencyContact, HealthHistory, MedicalReport, Reminder, SmartwatchData
from .serializers import (
    EmergencyContactSerializer,
    HealthHistorySerializer,
    MedicalReportSerializer,
    ReminderSerializer,
    SmartwatchDataSerializer,
)
from .sms_gateway import SMSDeliveryError, is_fast2sms_configured, send_fast2sms_sms
from users.models import Profile
from users.serializers import DeviceStateSerializer

MAX_EMERGENCY_CONTACTS = 5
ALERT_REPEAT_INTERVAL_SECONDS = 60

DEVICE_STATE_FIELDS = (
    'phone_permission_granted',
    'location_permission_granted',
    'latitude',
    'longitude',
    'location_timestamp',
)


def _sync_runtime_device_state(profile, request_data):
    payload = {
        field_name: request_data.get(field_name)
        for field_name in DEVICE_STATE_FIELDS
        if field_name in request_data
    }
    if not payload:
        return

    serializer = DeviceStateSerializer(profile, data=payload, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()


def _build_location_payload(profile):
    has_coordinates = profile.latitude is not None and profile.longitude is not None
    maps_url = None
    if has_coordinates:
        maps_url = f'https://maps.google.com/?q={profile.latitude},{profile.longitude}'

    return {
        'latitude': profile.latitude,
        'longitude': profile.longitude,
        'timestamp': profile.location_timestamp,
        'available': has_coordinates,
        'maps_url': maps_url,
    }


def _build_health_payload(profile, latest_sw, result):
    return {
        'heart_rate': latest_sw.heart_rate,
        'spo2': latest_sw.spo2,
        'systolic_bp': profile.systolic_bp,
        'diastolic_bp': profile.diastolic_bp,
        'blood_pressure': f'{profile.systolic_bp}/{profile.diastolic_bp} mmHg',
        'prediction': result,
    }


def _build_action_requirements(contacts, primary_contact, profile, location_payload):
    sms_missing = []
    dial_missing = []

    if not contacts:
        sms_missing.append('emergency_contacts')
        dial_missing.append('emergency_contacts')

    if not profile.location_permission_granted:
        sms_missing.append('location_permission')

    if not location_payload['available']:
        sms_missing.append('live_location')

    if not is_fast2sms_configured():
        sms_missing.append('sms_provider_not_configured')

    if primary_contact is None and 'emergency_contacts' not in dial_missing:
        dial_missing.append('priority_contact')

    return sms_missing, dial_missing


def _build_sms_message(user, profile, health_payload, location_payload):
    display_name = user.get_full_name() or user.username
    lines = [
        'AROGYALINK CRITICAL ALERT',
        f'Patient: {display_name}',
        f'Contact: {profile.phone_number or "Not available"}',
        f'Heart Rate: {health_payload["heart_rate"]} bpm',
        f'BP: {health_payload["blood_pressure"]}',
    ]
    if health_payload['spo2'] is not None:
        lines.append(f'SpO2: {health_payload["spo2"]}%')
    lines.append(f'Location: {location_payload["maps_url"] or "Not available"}')
    lines.append('Please reach the user immediately.')
    return '\n'.join(lines)


def _normalize_phone_uri_number(phone_number):
    value = str(phone_number or '').strip()
    if not value:
        return None

    if value.startswith('+'):
        digits = ''.join(ch for ch in value[1:] if ch.isdigit())
        return f'+{digits}' if digits else None

    digits = ''.join(ch for ch in value if ch.isdigit())
    return digits or None


def _build_sms_targets(contacts, message):
    encoded_message = quote(message, safe='')
    targets = []
    for contact in contacts:
        sms_phone_number = _normalize_phone_uri_number(contact.phone_number)
        targets.append(
            {
                'name': contact.name,
                'relation': contact.relation,
                'phone_number': contact.phone_number,
                'priority': contact.priority,
                'sms_uri_number': sms_phone_number,
                'sms_uri': (
                    f'sms:{sms_phone_number}?body={encoded_message}' if sms_phone_number else None
                ),
            }
        )
    return targets


def _reset_critical_alert_tracking(profile):
    fields_to_update = []

    if profile.critical_alert_active:
        profile.critical_alert_active = False
        fields_to_update.append('critical_alert_active')

    if profile.last_critical_message_sent_at is not None:
        profile.last_critical_message_sent_at = None
        fields_to_update.append('last_critical_message_sent_at')

    if fields_to_update:
        profile.save(update_fields=fields_to_update)


def _activate_critical_episode(profile):
    if profile.critical_alert_active:
        return False

    profile.critical_alert_active = True
    profile.save(update_fields=['critical_alert_active'])
    return True


def _mark_critical_message_sent(profile, sent_at):
    profile.last_critical_message_sent_at = sent_at
    profile.save(update_fields=['last_critical_message_sent_at'])


def _build_repeat_schedule(profile, message_channel_ready, *, now=None):
    now = now or timezone.now()
    is_new_critical_episode = not profile.critical_alert_active
    last_dispatch_at = profile.last_critical_message_sent_at
    should_dispatch_now = False

    if message_channel_ready and (
        last_dispatch_at is None
        or now >= last_dispatch_at + timedelta(seconds=ALERT_REPEAT_INTERVAL_SECONDS)
    ):
        should_dispatch_now = True

    next_dispatch_at = None
    seconds_until_next_dispatch = 0
    if last_dispatch_at is not None:
        next_dispatch_at = last_dispatch_at + timedelta(seconds=ALERT_REPEAT_INTERVAL_SECONDS)
        if not should_dispatch_now:
            seconds_until_next_dispatch = max(0, int((next_dispatch_at - now).total_seconds()))

    return {
        'repeat_interval_seconds': ALERT_REPEAT_INTERVAL_SECONDS,
        'repeat_interval_minutes': ALERT_REPEAT_INTERVAL_SECONDS // 60,
        'repeat_while_prediction_is_critical': True,
        'is_new_critical_episode': is_new_critical_episode,
        'should_dispatch_now': should_dispatch_now,
        'last_dispatch_at': last_dispatch_at,
        'next_dispatch_at': next_dispatch_at,
        'seconds_until_next_dispatch': seconds_until_next_dispatch,
    }


def _build_sms_delivery_result(*, attempted, sent, details=None, error=None):
    return {
        'provider': 'fast2sms',
        'attempted': attempted,
        'sent': sent,
        'details': details,
        'error': error,
    }


def _send_critical_sms_if_due(profile, contacts, message, repeat_schedule):
    if not repeat_schedule['should_dispatch_now']:
        return _build_sms_delivery_result(attempted=False, sent=False)

    contact_numbers = [contact.phone_number for contact in contacts]
    try:
        delivery = send_fast2sms_sms(message, contact_numbers)
        sent_at = timezone.now()
        _mark_critical_message_sent(profile, sent_at)
        repeat_schedule['last_dispatch_at'] = sent_at
        repeat_schedule['next_dispatch_at'] = sent_at + timedelta(seconds=ALERT_REPEAT_INTERVAL_SECONDS)
        repeat_schedule['seconds_until_next_dispatch'] = ALERT_REPEAT_INTERVAL_SECONDS
        return _build_sms_delivery_result(attempted=True, sent=True, details=delivery)
    except SMSDeliveryError as exc:
        return _build_sms_delivery_result(
            attempted=True,
            sent=False,
            error={
                'message': str(exc),
                'status_code': exc.status_code,
                'payload': exc.payload,
            },
        )


class MedicalReportViewSet(viewsets.ModelViewSet):
    serializer_class = MedicalReportSerializer

    def get_queryset(self):
        return MedicalReport.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SmartwatchDataViewSet(viewsets.ModelViewSet):
    serializer_class = SmartwatchDataSerializer

    def get_queryset(self):
        return SmartwatchData.objects.filter(user=self.request.user).order_by('-timestamp')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class HealthHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = HealthHistorySerializer

    def get_queryset(self):
        return HealthHistory.objects.filter(user=self.request.user).order_by('-timestamp')


class EmergencyContactViewSet(viewsets.ModelViewSet):
    serializer_class = EmergencyContactSerializer

    def get_queryset(self):
        return EmergencyContact.objects.filter(user=self.request.user).order_by('priority', 'id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReminderViewSet(viewsets.ModelViewSet):
    serializer_class = ReminderSerializer

    def get_queryset(self):
        return Reminder.objects.filter(user=self.request.user).order_by('time')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PredictionView(APIView):
    def post(self, request):
        user = request.user
        try:
            profile = user.profile
        except Profile.DoesNotExist:
            return Response({'error': 'Please complete your profile first.'}, status=status.HTTP_400_BAD_REQUEST)

        _sync_runtime_device_state(profile, request.data)

        latest_sw = SmartwatchData.objects.filter(user=user).order_by('-timestamp').first()
        if not latest_sw:
            return Response(
                {'error': 'Please upload smartwatch data before requesting a prediction.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        heart_rate = latest_sw.heart_rate

        features = {
            'Age': profile.age,
            'Sex': profile.sex,
            'Cholesterol': profile.cholesterol,
            'Heart Rate': heart_rate,
            'Diabetes': 1 if profile.diabetes else 0,
            'Smoking': 1 if profile.smoking else 0,
            'Obesity': 1 if profile.obesity else 0,
            'Alcohol Consumption': 1 if profile.alcohol_consumption else 0,
            'Exercise Hours Per Week': profile.exercise_hours_per_week,
            'Previous Heart Problems': 1 if profile.previous_heart_problems else 0,
            'Medication Use': 1 if profile.medication_use else 0,
            'Stress Level': profile.stress_level,
            'Sedentary Hours Per Day': profile.sedentary_hours_per_day,
            'BMI': profile.bmi,
            'Triglycerides': profile.triglycerides,
            'Physical Activity Days Per Week': profile.physical_activity_days_per_week,
            'Sleep Hours Per Day': profile.sleep_hours_per_day,
            'Systolic': profile.systolic_bp,
            'Diastolic': profile.diastolic_bp,
            'Diet_Average': 1 if profile.diet == 1 else 0,
            'Diet_Healthy': 1 if profile.diet == 2 else 0,
            'Diet_Unhealthy': 1 if profile.diet == 0 else 0,
        }

        result = ml_utils.predict_heart_risk(features)
        if result in {'Model Error', 'Error'}:
            detail = ml_utils.MODEL_LOAD_ERROR or 'Prediction model could not be loaded.'
            return Response(
                {'error': f'Prediction service unavailable. {detail}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        history = HealthHistory.objects.create(
            user=user,
            prediction_result=result,
            heart_rate_snapshot=heart_rate,
            systolic_bp_snapshot=profile.systolic_bp,
            diastolic_bp_snapshot=profile.diastolic_bp,
        )

        response_data = {
            'prediction': result,
            'timestamp': history.timestamp,
            'alert': result == 'Critical',
        }

        if result != 'Critical':
            _reset_critical_alert_tracking(profile)

        if result == 'Critical':
            contacts = list(
                EmergencyContact.objects.filter(user=user).order_by('priority', 'id')[:MAX_EMERGENCY_CONTACTS]
            )
            primary_contact = contacts[0] if contacts else None
            location_payload = _build_location_payload(profile)
            health_payload = _build_health_payload(profile, latest_sw, result)
            sms_message = _build_sms_message(user, profile, health_payload, location_payload)
            sms_targets = _build_sms_targets(contacts, sms_message)
            contact_payload = [
                {
                    'name': contact.name,
                    'relation': contact.relation,
                    'phone_number': contact.phone_number,
                    'priority': contact.priority,
                }
                for contact in contacts
            ]
            sms_missing_requirements, dial_missing_requirements = _build_action_requirements(
                contacts,
                primary_contact,
                profile,
                location_payload,
            )
            sms_ready = not sms_missing_requirements
            dial_ready = not dial_missing_requirements
            repeat_schedule = _build_repeat_schedule(profile, message_channel_ready=sms_ready)
            is_new_critical_episode = _activate_critical_episode(profile)
            repeat_schedule['is_new_critical_episode'] = is_new_critical_episode
            sms_delivery = (
                _send_critical_sms_if_due(profile, contacts, sms_message, repeat_schedule)
                if sms_ready
                else _build_sms_delivery_result(attempted=False, sent=False)
            )
            should_open_dialer = dial_ready and is_new_critical_episode
            dial_phone_number = _normalize_phone_uri_number(primary_contact.phone_number) if primary_contact else None

            response_data['emergency_alert_sent_to'] = [contact.phone_number for contact in contacts]
            response_data['sms_targets'] = sms_targets
            response_data['sms_message'] = sms_message
            response_data['simple_message'] = sms_message
            response_data['alert_repeat'] = repeat_schedule
            response_data['sms_delivery'] = sms_delivery
            response_data['client_permissions'] = {
                'location_permission_granted': profile.location_permission_granted,
            }
            response_data['client_actions'] = {
                'request_location_permission': not profile.location_permission_granted,
                'sms_sent_by_backend': sms_delivery['sent'],
                'open_dialer_for_primary_contact': should_open_dialer,
            }
            response_data['dial_action'] = {
                'should_open_dialer': should_open_dialer,
                'target': (
                    {
                        'name': primary_contact.name,
                        'relation': primary_contact.relation,
                        'phone_number': primary_contact.phone_number,
                        'priority': primary_contact.priority,
                        'dial_uri': f'tel:{dial_phone_number}' if dial_phone_number else None,
                    }
                    if primary_contact
                    else None
                ),
            }
            response_data['delivery_channels'] = {
                'sms': {
                    'ready': sms_ready,
                    'message': sms_message,
                    'targets': sms_targets,
                    'should_dispatch_now': repeat_schedule['should_dispatch_now'],
                    'backend_delivery': sms_delivery,
                },
                'dialer': {
                    'ready': dial_ready,
                    'target': response_data['dial_action']['target'],
                    'should_dispatch_now': should_open_dialer,
                },
            }
            response_data['missing_requirements'] = {
                'sms': sms_missing_requirements,
                'dialer': dial_missing_requirements,
            }
            response_data['emergency_actions_ready'] = sms_ready and dial_ready
            response_data['emergency_payload'] = {
                'user': {
                    'name': user.get_full_name() or user.username,
                    'email': user.email,
                    'phone_number': profile.phone_number,
                    'location': location_payload,
                },
                'health_details': health_payload,
                'contacts': contact_payload,
                'permissions': response_data['client_permissions'],
                'sms_targets': sms_targets,
                'sms_message': sms_message,
                'sms_delivery': sms_delivery,
                'dial_target': response_data['dial_action']['target'],
                'action_readiness': {
                    'sms_ready': sms_ready,
                    'dial_ready': dial_ready,
                },
                'repeat_schedule': repeat_schedule,
                'missing_requirements': response_data['missing_requirements'],
            }
            response_data['message'] = (
                'CRITICAL CONDITION DETECTED! Backend sent the SMS alert and the client should open the dialer for the '
                'highest-priority contact. Backend retries SMS every 1 minute while prediction remains critical.'
                if response_data['emergency_actions_ready'] and sms_delivery['sent']
                else 'CRITICAL CONDITION DETECTED! SMS backend delivery status, dialer readiness, and the 1-minute repeat '
                     'schedule are included in the response.'
            )

        return Response(response_data)
