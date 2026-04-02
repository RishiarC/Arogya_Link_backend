from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class Profile(models.Model):
    SEX_CHOICES = (
        (1, 'Male'),
        (0, 'Female'),
    )
    DIET_CHOICES = (
        (0, 'Unhealthy'),
        (1, 'Average'),
        (2, 'Healthy'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    age = models.IntegerField(default=30)
    sex = models.IntegerField(choices=SEX_CHOICES, default=1)

    # Device and location data
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    location_timestamp = models.DateTimeField(blank=True, null=True)

    # Static Report/Historical Data
    cholesterol = models.IntegerField(default=200)
    systolic_bp = models.IntegerField(default=120)
    diastolic_bp = models.IntegerField(default=80)
    diabetes = models.BooleanField(default=False)
    smoking = models.BooleanField(default=False)
    obesity = models.BooleanField(default=False)
    alcohol_consumption = models.BooleanField(default=False)
    previous_heart_problems = models.BooleanField(default=False)
    medication_use = models.BooleanField(default=False)
    triglycerides = models.IntegerField(default=150)
    bmi = models.FloatField(default=22.0)
    
    # Lifestyle Data
    diet = models.IntegerField(choices=DIET_CHOICES, default=1)
    exercise_hours_per_week = models.FloatField(default=5.0)
    stress_level = models.IntegerField(default=5) # 1 to 10
    sedentary_hours_per_day = models.FloatField(default=8.0)
    physical_activity_days_per_week = models.IntegerField(default=3)
    sleep_hours_per_day = models.IntegerField(default=7)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class EmailOTP(models.Model):
    PURPOSE_CHOICES = (
        ('register', 'Register'),
        ('reset_password', 'Reset Password'),
    )

    email = models.EmailField()
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='register')
    code = models.CharField(max_length=5)
    created_at = models.DateTimeField(default=timezone.now)
    last_sent_at = models.DateTimeField(default=timezone.now)
    is_used = models.BooleanField(default=False)

    class Meta:
        unique_together = ('email', 'purpose')

    def is_valid(self):
        return (
            not self.is_used and
            timezone.now() - self.created_at <= timedelta(minutes=15)
        )

    def can_resend(self):
        return timezone.now() - self.last_sent_at >= timedelta(seconds=60)

    def __str__(self):
        return f"OTP for {self.email} ({self.purpose}) - {'used' if self.is_used else 'active'}"
