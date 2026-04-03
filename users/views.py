from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
import random

from .models import Profile, EmailOTP
from .serializers import UserSerializer, ProfileSerializer, DeviceStateSerializer


def generate_otp():
    return f"{random.randint(10000, 99999)}"


def validate_user_password(password, user=None):
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        raise ValueError(list(exc.messages))


def send_otp_email(email, subject, message, otp_code):
    if getattr(settings, "OTP_ECHO_TO_CONSOLE", True):
        print(f"[OTP] {email} -> {otp_code} ({subject})")

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    send_mail(subject, message, from_email, [email], fail_silently=False)

class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({'error': 'Email already registered.'}, status=status.HTTP_400_BAD_REQUEST)

        otp_code = generate_otp()
        otp_record, created = EmailOTP.objects.get_or_create(
            email=email,
            purpose='register',
            defaults={
                'code': otp_code,
                'is_used': False,
                'created_at': timezone.now(),
                'last_sent_at': timezone.now(),
            }
        )

        if not created and not otp_record.can_resend():
            return Response({'error': 'Please wait 1 minute before resending OTP.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        otp_record.code = otp_code
        otp_record.is_used = False
        otp_record.created_at = timezone.now()
        otp_record.last_sent_at = timezone.now()
        otp_record.save()

        subject = 'ArogyaLink Registration OTP'
        message = f'Your ArogyaLink registration OTP is {otp_code}. It expires in 15 minutes.'

        try:
            send_otp_email(email, subject, message, otp_code)
        except Exception as e:
            return Response({'error': f'Failed to send OTP email. {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'detail': 'OTP sent to email and echoed in server console. Verify it with /verify-otp/'}, status=status.HTTP_202_ACCEPTED)

class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        password = request.data.get('password')
        username = request.data.get('username') or email

        if not email or not otp or not password:
            return Response(
                {'error': 'Email, OTP, and password are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            otp_record = EmailOTP.objects.get(email=email, code=otp, is_used=False)
        except EmailOTP.DoesNotExist:
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if not otp_record.is_valid():
            return Response({'error': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({'error': 'Email already registered.'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            username = email

        profile_data = request.data.get('profile', {}) or {}
        try:
            validate_user_password(password)
        except ValueError as exc:
            return Response({'password': exc.args[0]}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, email=email, password=password)
        Profile.objects.create(user=user, **profile_data)

        otp_record.is_used = True
        otp_record.save()

        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)

class ResendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        purpose = request.data.get('purpose', 'register')

        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            otp_record = EmailOTP.objects.get(email=email, purpose=purpose)
        except EmailOTP.DoesNotExist:
            return Response({'error': 'No OTP request found for this email/purpose.'}, status=status.HTTP_404_NOT_FOUND)

        if not otp_record.can_resend():
            return Response({'error': 'Please wait 1 minute before resending OTP.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        otp_record.code = generate_otp()
        otp_record.created_at = timezone.now()
        otp_record.last_sent_at = timezone.now()
        otp_record.is_used = False
        otp_record.save()

        subject = 'ArogyaLink OTP Resend'
        message = f'Your ArogyaLink {purpose} OTP is {otp_record.code}. It expires in 15 minutes.'

        try:
            send_otp_email(email, subject, message, otp_record.code)
        except Exception as e:
            return Response({'error': f'Failed to resend OTP email. {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'detail': 'OTP resent to email.'}, status=status.HTTP_200_OK)

class ForgotPasswordRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not User.objects.filter(email=email).exists():
            return Response({'error': 'Email is not registered.'}, status=status.HTTP_400_BAD_REQUEST)

        otp_code = generate_otp()
        otp_record, created = EmailOTP.objects.get_or_create(
            email=email,
            purpose='reset_password',
            defaults={
                'code': otp_code,
                'is_used': False,
                'created_at': timezone.now(),
                'last_sent_at': timezone.now(),
            }
        )

        if not created and not otp_record.can_resend():
            return Response({'error': 'Please wait 1 minute before resending OTP.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        otp_record.code = otp_code
        otp_record.is_used = False
        otp_record.created_at = timezone.now()
        otp_record.last_sent_at = timezone.now()
        otp_record.save()

        subject = 'ArogyaLink Password Reset OTP'
        message = f'Your ArogyaLink password reset OTP is {otp_code}. It expires in 15 minutes.'
        try:
            send_otp_email(email, subject, message, otp_code)
        except Exception as e:
            return Response({'error': f'Failed to send OTP email. {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'detail': 'OTP sent to email. Verify it with /reset-password/.'}, status=status.HTTP_202_ACCEPTED)

class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('password')

        if not email or not otp or not new_password:
            return Response({'error': 'Email, OTP, and new password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            otp_record = EmailOTP.objects.get(email=email, purpose='reset_password', code=otp, is_used=False)
        except EmailOTP.DoesNotExist:
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        if not otp_record.is_valid():
            return Response({'error': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            validate_user_password(new_password, user=user)
        except ValueError as exc:
            return Response({'password': exc.args[0]}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        otp_record.is_used = True
        otp_record.save()

        return Response({'detail': 'Password has been reset successfully.'}, status=status.HTTP_200_OK)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        username = request.data.get('username')
        password = request.data.get('password')

        if email and not username:
            try:
                username = User.objects.get(email=email).username
            except User.DoesNotExist:
                return Response({'error': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        if not username or not password:
            return Response({'error': 'Username/email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if user:
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'user': UserSerializer(user).data,
                'token': token.key
            })
        return Response({'error': 'Invalid Credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class ProfileViewSet(viewsets.ModelViewSet):
    serializer_class = ProfileSerializer

    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    # Helper to get the single profile of the logged-in user
    def list(self, request, *args, **kwargs):
        profile = self.get_queryset().first()
        if profile:
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['patch', 'post'], url_path='device-state')
    def device_state(self, request, *args, **kwargs):
        profile = self.get_queryset().first()
        if not profile:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = DeviceStateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
