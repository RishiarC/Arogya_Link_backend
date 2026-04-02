# ArogyaLink Backend

Backend API for ArogyaLink, built with Django and Django REST Framework.  
This project handles user authentication, OTP verification, profile management, health data storage, and heart-risk prediction using a trained machine learning model.

## Overview

This backend provides:

- Email OTP based registration
- Login with token authentication
- Forgot password and reset password via OTP
- User profile management
- Smartwatch data storage
- Medical report upload support
- Emergency contact management
- Reminder management
- Heart risk prediction using an ML model
- Prediction history tracking

## Tech Stack

- Python
- Django 6
- Django REST Framework
- SQLite
- Pandas
- Scikit-learn
- Joblib
- XGBoost
- Pillow

## Project Structure

```text
App_backend/
|-- arogyalink_backend/
|   |-- settings.py
|   |-- urls.py
|   |-- asgi.py
|   `-- wsgi.py
|-- users/
|   |-- models.py
|   |-- serializers.py
|   |-- urls.py
|   `-- views.py
|-- health/
|   |-- models.py
|   |-- serializers.py
|   |-- urls.py
|   |-- views.py
|   `-- ml_utils.py
|-- ML_model/
|   `-- arogya_link_ensemble_model2.pkl
|-- media/
|-- manage.py
|-- requirements.txt
|-- verify_backend.py
|-- .env.example
`-- README.md
```

## Main Apps

### `users`

Responsible for:

- Registration OTP generation
- OTP verification and account creation
- Login
- Forgot password OTP
- Password reset
- User profile CRUD

### `health`

Responsible for:

- Medical report uploads
- Smartwatch data
- Prediction history
- Emergency contacts
- Reminders
- ML prediction endpoint

## Authentication

The project uses:

- `TokenAuthentication`
- `SessionAuthentication`

Most endpoints require authentication by default.

Use token in request headers:

```http
Authorization: Token YOUR_TOKEN_HERE
```

## Environment Configuration

The project automatically loads variables from a local `.env` file if present.

Use `.env.example` as reference.

### Recommended `.env`

```env
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,testserver
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=yourgmail@gmail.com
EMAIL_HOST_PASSWORD=your_16_char_gmail_app_password
DEFAULT_FROM_EMAIL=ArogyaLink <yourgmail@gmail.com>
OTP_ECHO_TO_CONSOLE=True
```

### Important Environment Variables

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key |
| `DJANGO_DEBUG` | Enable or disable debug mode |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `SQLITE_NAME` | Override SQLite database path |
| `EMAIL_BACKEND` | SMTP or console backend |
| `EMAIL_HOST` | SMTP host |
| `EMAIL_PORT` | SMTP port |
| `EMAIL_USE_TLS` | TLS on/off |
| `EMAIL_HOST_USER` | Sender Gmail |
| `EMAIL_HOST_PASSWORD` | Gmail App Password |
| `DEFAULT_FROM_EMAIL` | Sender display address |
| `OTP_ECHO_TO_CONSOLE` | Also print OTP in terminal |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins |

## Local Setup

### 1. Create and activate virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run migrations

```powershell
python manage.py migrate
```

### 4. Start the server

```powershell
python manage.py runserver
```

Server base URL:

```text
http://127.0.0.1:8000/
```

## OTP and Email Behavior

The backend supports both:

- Sending OTP to Gmail via SMTP
- Printing OTP in server terminal

If `OTP_ECHO_TO_CONSOLE=True`, the terminal shows lines like:

```text
[OTP] yourmail@example.com -> 12345 (ArogyaLink Registration OTP)
```

If Gmail SMTP is configured correctly, the same OTP is also sent to the user's inbox.

### Gmail Requirements

- Use Gmail address in `EMAIL_HOST_USER`
- Use Google App Password in `EMAIL_HOST_PASSWORD`
- Do not use your normal Gmail password
- Restart server after changing `.env`

## API Base Routes

### Root routing

- `/api/users/`
- `/api/health/`
- `/admin/`

## User and Auth APIs

### `POST /api/users/register/`

Starts registration by sending OTP to email.

Request body:

```json
{
  "email": "user@example.com"
}
```

### `POST /api/users/verify-otp/`

Verifies registration OTP and creates user account.

Request body:

```json
{
  "email": "user@example.com",
  "otp": "12345",
  "password": "StrongPassword123!",
  "username": "user@example.com",
  "profile": {
    "age": 22,
    "sex": 1
  }
}
```

Response includes:

- `user`
- `token`

### `POST /api/users/login/`

Login using username or email plus password.

Request body:

```json
{
  "email": "user@example.com",
  "password": "StrongPassword123!"
}
```

### `POST /api/users/resend-otp/`

Resends OTP for registration or password reset.

Request body:

```json
{
  "email": "user@example.com",
  "purpose": "register"
}
```

Possible `purpose` values:

- `register`
- `reset_password`

### `POST /api/users/forgot-password/`

Sends reset-password OTP.

Request body:

```json
{
  "email": "user@example.com"
}
```

### `POST /api/users/reset-password/`

Resets password using OTP.

Request body:

```json
{
  "email": "user@example.com",
  "otp": "12345",
  "password": "NewStrongPassword123!"
}
```

### Profile API

Router path:

- `GET /api/users/profile/`
- `POST /api/users/profile/`
- `PUT /api/users/profile/{id}/`
- `PATCH /api/users/profile/{id}/`
- `DELETE /api/users/profile/{id}/`

Notes:

- `GET /api/users/profile/` returns the logged-in user's profile
- Profile is linked one-to-one with the authenticated user

## Health APIs

### Medical Reports

Router path:

- `GET /api/health/reports/`
- `POST /api/health/reports/`
- `GET /api/health/reports/{id}/`
- `PUT /api/health/reports/{id}/`
- `PATCH /api/health/reports/{id}/`
- `DELETE /api/health/reports/{id}/`

Fields:

- `report_image`
- `description`

### Smartwatch Data

Router path:

- `GET /api/health/smartwatch/`
- `POST /api/health/smartwatch/`
- `GET /api/health/smartwatch/{id}/`
- `PUT /api/health/smartwatch/{id}/`
- `PATCH /api/health/smartwatch/{id}/`
- `DELETE /api/health/smartwatch/{id}/`

Request body example:

```json
{
  "heart_rate": 92,
  "spo2": 98
}
```

### Prediction History

Read-only router path:

- `GET /api/health/history/`
- `GET /api/health/history/{id}/`

### Emergency Contacts

Router path:

- `GET /api/health/contacts/`
- `POST /api/health/contacts/`
- `GET /api/health/contacts/{id}/`
- `PUT /api/health/contacts/{id}/`
- `PATCH /api/health/contacts/{id}/`
- `DELETE /api/health/contacts/{id}/`

Request body example:

```json
{
  "name": "John Doe",
  "relation": "Brother",
  "phone_number": "9876543210"
}
```

### Reminders

Router path:

- `GET /api/health/reminders/`
- `POST /api/health/reminders/`
- `GET /api/health/reminders/{id}/`
- `PUT /api/health/reminders/{id}/`
- `PATCH /api/health/reminders/{id}/`
- `DELETE /api/health/reminders/{id}/`

Request body example:

```json
{
  "title": "Take medicine",
  "reminder_type": "Medicine",
  "time": "2026-04-03T08:30:00Z",
  "is_completed": false
}
```

### `POST /api/health/predict/`

Runs heart-risk prediction for the authenticated user.

Request body:

```json
{}
```

Prediction uses:

- User profile data
- Latest smartwatch heart-rate data

Requirements before prediction:

- User must be authenticated
- User profile must exist
- At least one smartwatch data record must exist
- ML model must load successfully

Possible response:

```json
{
  "prediction": "Normal",
  "timestamp": "2026-04-02T18:31:36.199941Z",
  "alert": false
}
```

Critical response may also include:

- `emergency_alert_sent_to`
- `emergency_payload`
- `message`

## Prediction Model

Model file:

```text
ML_model/arogya_link_ensemble_model2.pkl
```

Current prediction input uses 22 features:

1. Age
2. Sex
3. Cholesterol
4. Heart Rate
5. Diabetes
6. Smoking
7. Obesity
8. Alcohol Consumption
9. Exercise Hours Per Week
10. Previous Heart Problems
11. Medication Use
12. Stress Level
13. Sedentary Hours Per Day
14. BMI
15. Triglycerides
16. Physical Activity Days Per Week
17. Sleep Hours Per Day
18. Systolic
19. Diastolic
20. Diet_Average
21. Diet_Healthy
22. Diet_Unhealthy

The backend now aligns prediction order with the model's actual `feature_names_in_` when available.

## Data Models Summary

### `users.Profile`

Stores:

- Age and sex
- Phone number
- Latitude and longitude
- Cholesterol and blood pressure
- Diabetes, smoking, obesity
- Alcohol use
- Previous heart problems
- Medication use
- Triglycerides
- BMI
- Diet
- Exercise, stress, sedentary time
- Physical activity days
- Sleep hours

### `users.EmailOTP`

Stores:

- Email
- Purpose
- OTP code
- Created time
- Last sent time
- Used/not used status

### `health.MedicalReport`

Stores uploaded report image and description.

### `health.SmartwatchData`

Stores:

- Heart rate
- SpO2
- Timestamp

### `health.HealthHistory`

Stores:

- Prediction result
- Heart rate snapshot
- Systolic BP snapshot
- Diastolic BP snapshot
- Timestamp

### `health.EmergencyContact`

Stores:

- Name
- Relation
- Phone number

### `health.Reminder`

Stores:

- Title
- Reminder type
- Time
- Completion status

## Password Rules

Password validation uses Django validators:

- Minimum length
- Common password rejection
- Numeric-only password rejection
- User similarity validation

These rules are enforced in:

- Registration verification
- Password reset

## Development Commands

### Run system check

```powershell
python manage.py check
```

### Run project verification script

```powershell
python verify_backend.py
```

### Run tests

```powershell
python manage.py test
```

Note:

- `verify_backend.py` performs a practical flow check
- test suite currently has no real automated test coverage

## Troubleshooting

### OTP email not received

Check:

- `.env` exists
- `EMAIL_HOST_USER` is correct
- `EMAIL_HOST_PASSWORD` is a Gmail App Password
- server restarted after config change
- spam folder
- terminal output for OTP echo

### Prediction returns model error

Check:

- server restarted after model-related changes
- smartwatch data exists for the user
- profile exists for the user
- required ML dependencies are available

### SQLite disk I/O issue

If SQLite file causes sync or OneDrive related issues, set:

```env
SQLITE_NAME=C:\path\to\another\db.sqlite3
```

## Security Notes

- Do not commit `.env`
- Use a real `DJANGO_SECRET_KEY` in production
- Set `DJANGO_DEBUG=False` in production
- Restrict `CORS_ALLOWED_ORIGINS` in production
- Rotate exposed Gmail App Password if it was ever shared publicly

## Current Status

The backend currently supports:

- OTP registration and verification
- Token login
- Password reset via OTP
- Profile APIs
- Health CRUD APIs
- Prediction endpoint
- Gmail plus console OTP flow
- Local `.env` configuration

## Suggested Next Improvements

- Add real automated tests
- Add `.env` validation
- Add API documentation with Swagger or ReDoc
- Add production settings split
- Re-export or retrain ML model with pinned dependency versions
- Add background jobs for actual emergency notifications
