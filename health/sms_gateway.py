import json
import os
from typing import Iterable
from urllib import error, parse, request


FAST2SMS_BULK_URL = 'https://www.fast2sms.com/dev/bulkV2'


class SMSDeliveryError(Exception):
    def __init__(self, message, *, payload=None, status_code=None):
        super().__init__(message)
        self.payload = payload
        self.status_code = status_code


def is_fast2sms_configured():
    return bool(os.environ.get('FAST2SMS_API_KEY'))


def send_fast2sms_sms(message: str, numbers: Iterable[str]):
    api_key = os.environ.get('FAST2SMS_API_KEY')
    if not api_key:
        raise SMSDeliveryError('Fast2SMS API key is not configured.')

    normalized_numbers = [str(number).strip() for number in numbers if str(number).strip()]
    if not normalized_numbers:
        raise SMSDeliveryError('No valid phone numbers were provided for Fast2SMS delivery.')

    payload = {
        'route': os.environ.get('FAST2SMS_ROUTE', 'q'),
        'message': message,
        'language': os.environ.get('FAST2SMS_LANGUAGE', 'english'),
        'numbers': ','.join(normalized_numbers),
        'flash': os.environ.get('FAST2SMS_FLASH', '0'),
    }

    encoded_body = parse.urlencode(payload).encode('utf-8')
    http_request = request.Request(
        FAST2SMS_BULK_URL,
        data=encoded_body,
        headers={
            'authorization': api_key,
            'Content-Type': 'application/x-www-form-urlencoded',
            'cache-control': 'no-cache',
        },
        method='POST',
    )

    timeout = float(os.environ.get('FAST2SMS_TIMEOUT_SECONDS', '15'))

    try:
        with request.urlopen(http_request, timeout=timeout) as response:
            raw_body = response.read().decode('utf-8')
            parsed_body = json.loads(raw_body)
            if not parsed_body.get('return'):
                raise SMSDeliveryError(
                    parsed_body.get('message', 'Fast2SMS delivery failed.'),
                    payload=parsed_body,
                    status_code=response.status,
                )
            return {
                'provider': 'fast2sms',
                'success': True,
                'status_code': response.status,
                'request_id': parsed_body.get('request_id'),
                'message': parsed_body.get('message'),
                'numbers': normalized_numbers,
                'raw': parsed_body,
            }
    except error.HTTPError as exc:
        raw_error_body = exc.read().decode('utf-8')
        try:
            parsed_error = json.loads(raw_error_body)
        except json.JSONDecodeError:
            parsed_error = {'message': raw_error_body or str(exc)}
        raise SMSDeliveryError(
            parsed_error.get('message', 'Fast2SMS request failed.'),
            payload=parsed_error,
            status_code=exc.code,
        ) from exc
    except error.URLError as exc:
        raise SMSDeliveryError(f'Fast2SMS network error: {exc.reason}') from exc
