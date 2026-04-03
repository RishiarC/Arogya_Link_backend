from unittest.mock import patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from users.models import Profile
from .models import EmergencyContact, SmartwatchData
from .sms_gateway import SMSDeliveryError


class EmergencyContactTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='contact-user',
            email='contact@example.com',
            password='StrongPass123!',
        )
        Profile.objects.create(user=self.user)
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_only_five_emergency_contacts_can_be_created(self):
        for index in range(1, 6):
            response = self.client.post(
                '/api/health/contacts/',
                {
                    'name': f'Contact {index}',
                    'relation': 'Friend',
                    'phone_number': f'99999999{index:02d}',
                    'priority': index,
                },
                format='json',
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        sixth_response = self.client.post(
            '/api/health/contacts/',
            {
                'name': 'Contact 6',
                'relation': 'Friend',
                'phone_number': '9999999906',
                'priority': 5,
            },
            format='json',
        )

        self.assertEqual(sixth_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Only 5 emergency contacts can be saved.', str(sixth_response.data))


class CriticalPredictionTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='critical-user',
            email='critical@example.com',
            password='StrongPass123!',
            first_name='Arogya',
            last_name='User',
        )
        self.profile = Profile.objects.create(
            user=self.user,
            phone_number='9876543210',
            location_permission_granted=True,
            latitude=28.6139,
            longitude=77.2090,
            systolic_bp=170,
            diastolic_bp=110,
            cholesterol=240,
        )
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        SmartwatchData.objects.create(user=self.user, heart_rate=126, spo2=93.0)
        EmergencyContact.objects.create(
            user=self.user,
            name='Primary Contact',
            relation='Brother',
            phone_number='9000000001',
            priority=1,
        )
        for priority in range(2, 6):
            EmergencyContact.objects.create(
                user=self.user,
                name=f'Contact {priority}',
                relation='Friend',
                phone_number=f'900000000{priority}',
                priority=priority,
            )

    @patch('health.views.send_fast2sms_sms')
    @patch('health.views.ml_utils.predict_heart_risk', return_value='Critical')
    def test_critical_prediction_sends_sms_and_returns_dial_payload(self, _mock_predict, mock_send_sms):
        mock_send_sms.return_value = {
            'provider': 'fast2sms',
            'success': True,
            'status_code': 200,
            'request_id': 'abc123',
            'message': ['Message sent successfully'],
            'numbers': ['9000000001', '9000000002', '9000000003', '9000000004', '9000000005'],
            'raw': {'return': True},
        }

        response = self.client.post('/api/health/predict/', {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['alert'])
        self.assertTrue(response.data['sms_delivery']['sent'])
        self.assertTrue(response.data['client_actions']['sms_sent_by_backend'])
        self.assertTrue(response.data['client_actions']['open_dialer_for_primary_contact'])
        self.assertEqual(len(response.data['sms_targets']), 5)
        self.assertEqual(response.data['dial_action']['target']['phone_number'], '9000000001')
        self.assertIn('Heart Rate: 126 bpm', response.data['sms_message'])
        self.assertIn('BP: 170/110 mmHg', response.data['sms_message'])
        self.assertIn('https://maps.google.com/?q=28.6139,77.209', response.data['sms_message'])
        self.assertTrue(response.data['alert_repeat']['should_dispatch_now'])
        self.assertEqual(response.data['alert_repeat']['repeat_interval_seconds'], 60)
        self.assertTrue(response.data['sms_targets'][0]['sms_uri'].startswith('sms:'))
        self.assertTrue(response.data['dial_action']['target']['dial_uri'].startswith('tel:'))
        self.assertEqual(response.data['missing_requirements']['sms'], [])
        self.assertEqual(response.data['missing_requirements']['dialer'], [])
        mock_send_sms.assert_called_once()

    @patch('health.views.send_fast2sms_sms')
    @patch('health.views.ml_utils.predict_heart_risk', return_value='Critical')
    def test_prediction_runtime_device_state_disables_sms_without_live_location(self, _mock_predict, mock_send_sms):
        response = self.client.post(
            '/api/health/predict/',
            {
                'location_permission_granted': False,
                'latitude': None,
                'longitude': None,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['client_actions']['sms_sent_by_backend'])
        self.assertTrue(response.data['client_actions']['open_dialer_for_primary_contact'])
        self.assertIn('location_permission', response.data['missing_requirements']['sms'])
        self.assertIn('live_location', response.data['missing_requirements']['sms'])
        self.assertEqual(response.data['missing_requirements']['dialer'], [])
        mock_send_sms.assert_not_called()

    @patch('health.views.send_fast2sms_sms')
    @patch('health.views.ml_utils.predict_heart_risk', return_value='Critical')
    def test_critical_messages_are_repeated_after_one_minute_not_every_request(self, _mock_predict, mock_send_sms):
        mock_send_sms.return_value = {
            'provider': 'fast2sms',
            'success': True,
            'status_code': 200,
            'request_id': 'abc123',
            'message': ['Message sent successfully'],
            'numbers': ['9000000001', '9000000002', '9000000003', '9000000004', '9000000005'],
            'raw': {'return': True},
        }

        first_response = self.client.post('/api/health/predict/', {}, format='json')
        second_response = self.client.post('/api/health/predict/', {}, format='json')

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertTrue(first_response.data['sms_delivery']['sent'])
        self.assertTrue(first_response.data['client_actions']['open_dialer_for_primary_contact'])
        self.assertFalse(second_response.data['sms_delivery']['attempted'])
        self.assertFalse(second_response.data['client_actions']['open_dialer_for_primary_contact'])
        self.assertGreater(second_response.data['alert_repeat']['seconds_until_next_dispatch'], 0)
        self.assertEqual(mock_send_sms.call_count, 1)

    @patch('health.views.send_fast2sms_sms', side_effect=SMSDeliveryError('Invalid Authentication', status_code=401))
    @patch('health.views.ml_utils.predict_heart_risk', return_value='Critical')
    def test_failed_sms_delivery_is_reported_without_starting_cooldown(self, _mock_predict, _mock_send_sms):
        first_response = self.client.post('/api/health/predict/', {}, format='json')
        second_response = self.client.post('/api/health/predict/', {}, format='json')

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertTrue(first_response.data['sms_delivery']['attempted'])
        self.assertFalse(first_response.data['sms_delivery']['sent'])
        self.assertEqual(first_response.data['sms_delivery']['error']['status_code'], 401)
        self.assertTrue(second_response.data['alert_repeat']['should_dispatch_now'])
