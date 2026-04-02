from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MedicalReportViewSet, SmartwatchDataViewSet, 
    HealthHistoryViewSet, EmergencyContactViewSet, 
    ReminderViewSet, PredictionView
)

router = DefaultRouter()
router.register(r'reports', MedicalReportViewSet, basename='reports')
router.register(r'smartwatch', SmartwatchDataViewSet, basename='smartwatch')
router.register(r'history', HealthHistoryViewSet, basename='history')
router.register(r'contacts', EmergencyContactViewSet, basename='contacts')
router.register(r'reminders', ReminderViewSet, basename='reminders')

urlpatterns = [
    path('predict/', PredictionView.as_view(), name='predict'),
    path('', include(router.urls)),
]
