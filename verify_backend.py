import os
import tempfile
import django
import json

# Setup Django environment
os.environ.setdefault(
    'SQLITE_NAME',
    os.path.join(tempfile.gettempdir(), 'arogyalink_verify.sqlite3')
)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arogyalink_backend.settings')
django.setup()

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from users.models import EmailOTP
import time

def verify_system():
    call_command('migrate', interactive=False, run_syncdb=True, verbosity=0)
    client = Client()
    
    print("--- 1. Testing Registration ---")
    unique_suffix = int(time.time())
    username = f"testuser_{unique_suffix}"
    email = f"test_{unique_suffix}@example.com"
    reg_data = {
        "username": username,
        "email": email,
    }
    url = reverse('register')
    print(f"Target URL: {url}")
    response = client.post(url, data=json.dumps(reg_data), content_type='application/json')
    print(f"Response Status: {response.status_code}")
    if response.status_code == 202:
        print("Registration OTP request accepted")
    else:
        try:
            print(f"Registration Failed. Errors: {response.json()}")
        except:
            print(f"Registration Failed. Content snippet: {response.content[:500]}")
        return

    otp_record = EmailOTP.objects.get(email=email, purpose='register')
    verify_data = {
        "username": username,
        "password": "StrongTestPassword123!",
        "email": email,
        "otp": otp_record.code,
        "profile": {
            "age": 45,
            "sex": 1,
            "bmi": 28.5,
            "systolic_bp": 140,
            "diastolic_bp": 90,
            "cholesterol": 240,
            "smoking": True
        }
    }

    print("\n--- 2. Verifying OTP ---")
    response = client.post(
        reverse('verify-otp'),
        data=json.dumps(verify_data),
        content_type='application/json'
    )
    print(f"Verify OTP Status: {response.status_code}")
    if response.status_code != 201:
        try:
            print(f"OTP Verification Failed. Errors: {response.json()}")
        except:
            print(f"OTP Verification Failed. Content snippet: {response.content[:500]}")
        return

    print("Registration Successful")
    token = response.json()['token']

    auth_headers = {'HTTP_AUTHORIZATION': f'Token {token}'}

    print("\n--- 3. Testing Profile Access ---")
    response = client.get('/api/users/profile/', **auth_headers)
    print(f"Profile: {response.json()}")

    print("\n--- 4. Pushing Smartwatch Data ---")
    sw_data = {"heart_rate": 105, "spo2": 96.5}
    response = client.post('/api/health/smartwatch/', data=sw_data, **auth_headers)
    print(f"Smartwatch Push: {response.status_code}")

    print("\n--- 5. Testing Prediction API ---")
    response = client.post('/api/health/predict/', **auth_headers)
    print(f"Prediction Result: {response.json()}")

    print("\n--- 6. Adding Emergency Contact ---")
    contact_data = {"name": "John Doe", "relation": "Brother", "phone_number": "9876543210"}
    response = client.post('/api/health/contacts/', data=contact_data, **auth_headers)
    print(f"Contact Added: {response.status_code}")

    print("\n--- 7. Testing History ---")
    response = client.get('/api/health/history/', **auth_headers)
    print(f"History Entries: {len(response.json())}")

    print("\nVerification Complete!")

if __name__ == "__main__":
    verify_system()
