from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, VerifyOTPView, ResendOTPView,
    ForgotPasswordRequestView, ResetPasswordView,
    LoginView, ProfileViewSet
)

router = DefaultRouter()
router.register(r'profile', ProfileViewSet, basename='profile')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('forgot-password/', ForgotPasswordRequestView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('login/', LoginView.as_view(), name='login'),
    path('', include(router.urls)),
]
