from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import MedicalReport, SmartwatchData, HealthHistory, EmergencyContact, Reminder
from .serializers import (
    MedicalReportSerializer, SmartwatchDataSerializer, 
    HealthHistorySerializer, EmergencyContactSerializer, ReminderSerializer
)
from . import ml_utils
from users.models import Profile

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
        return EmergencyContact.objects.filter(user=self.request.user)
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
        
        latest_sw = SmartwatchData.objects.filter(user=user).order_by('-timestamp').first()
        if not latest_sw:
            return Response(
                {'error': 'Please upload smartwatch data before requesting a prediction.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        heart_rate = latest_sw.heart_rate
        
        # Prepare features for the trained ML model (22 features).
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
            'Diet_Unhealthy': 1 if profile.diet == 0 else 0
        }
        
        result = ml_utils.predict_heart_risk(features)
        if result in {'Model Error', 'Error'}:
            detail = ml_utils.MODEL_LOAD_ERROR or 'Prediction model could not be loaded.'
            return Response(
                {'error': f'Prediction service unavailable. {detail}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Store in history
        history = HealthHistory.objects.create(
            user=user,
            prediction_result=result,
            heart_rate_snapshot=heart_rate,
            systolic_bp_snapshot=profile.systolic_bp,
            diastolic_bp_snapshot=profile.diastolic_bp
        )
        
        response_data = {
            'prediction': result,
            'timestamp': history.timestamp,
            'alert': result == 'Critical'
        }
        
        if result == 'Critical':
            # Emergency alert payload returned to the client for call/SMS handling.
            contacts = EmergencyContact.objects.filter(user=user)
            response_data['emergency_alert_sent_to'] = [c.phone_number for c in contacts]
            response_data['emergency_payload'] = {
                'user': {
                    'name': user.get_full_name() or user.username,
                    'email': user.email,
                    'phone_number': profile.phone_number,
                    'location': {
                        'latitude': profile.latitude,
                        'longitude': profile.longitude,
                        'timestamp': profile.location_timestamp,
                    }
                },
                'health_details': {
                    'heart_rate': heart_rate,
                    'systolic_bp': profile.systolic_bp,
                    'diastolic_bp': profile.diastolic_bp,
                    'prediction': result,
                },
                'contacts': [
                    {
                        'name': c.name,
                        'relation': c.relation,
                        'phone_number': c.phone_number
                    } for c in contacts
                ]
            }
            response_data['message'] = "CRITICAL CONDITION DETECTED! Emergency contacts notified."

        return Response(response_data)
