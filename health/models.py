from django.db import models
from django.contrib.auth.models import User

class MedicalReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='medical_reports')
    report_image = models.ImageField(upload_to='reports/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"Report for {self.user.username} - {self.uploaded_at}"

class SmartwatchData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='smartwatch_data')
    heart_rate = models.IntegerField()
    spo2 = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} HR: {self.heart_rate} at {self.timestamp}"

class HealthHistory(models.Model):
    RESULT_CHOICES = (
        ('Normal', 'Normal'),
        ('Medium', 'Medium'),
        ('Critical', 'Critical'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='health_histories')
    prediction_result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    # Storing a snapshot of inputs for history
    heart_rate_snapshot = models.IntegerField()
    systolic_bp_snapshot = models.IntegerField()
    diastolic_bp_snapshot = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.prediction_result} - {self.timestamp}"

class EmergencyContact(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emergency_contacts')
    name = models.CharField(max_length=100)
    relation = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=15)

    def __str__(self):
        return f"{self.name} ({self.relation}) - {self.user.username}"

class Reminder(models.Model):
    REMINDER_TYPE = (
        ('Medicine', 'Medicine'),
        ('Checkup', 'Checkup'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reminders')
    title = models.CharField(max_length=200)
    reminder_type = models.CharField(max_length=20, choices=REMINDER_TYPE)
    time = models.DateTimeField()
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} for {self.user.username}"
