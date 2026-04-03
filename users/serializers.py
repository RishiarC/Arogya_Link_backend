from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Profile

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = '__all__'
        read_only_fields = ('user',)


class DeviceStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = (
            'phone_permission_granted',
            'location_permission_granted',
            'latitude',
            'longitude',
            'location_timestamp',
        )

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        latitude = attrs.get('latitude', getattr(instance, 'latitude', None))
        longitude = attrs.get('longitude', getattr(instance, 'longitude', None))

        if latitude is not None and not -90 <= latitude <= 90:
            raise serializers.ValidationError({'latitude': 'Latitude must be between -90 and 90.'})

        if longitude is not None and not -180 <= longitude <= 180:
            raise serializers.ValidationError({'longitude': 'Longitude must be between -180 and 180.'})

        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError(
                {'location': 'Latitude and longitude must both be provided together or both be empty.'}
            )

        if 'latitude' in attrs or 'longitude' in attrs:
            if latitude is not None and longitude is not None and attrs.get('location_timestamp') is None:
                attrs['location_timestamp'] = timezone.now()
            elif latitude is None and longitude is None and 'location_timestamp' not in attrs:
                attrs['location_timestamp'] = None

        return attrs

class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'email', 'profile')
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True}
        }

    def validate_email(self, value):
        qs = User.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        username = validated_data.get('username') or validated_data.get('email')
        validated_data['username'] = username
        user = User.objects.create_user(**validated_data)
        Profile.objects.create(user=user, **profile_data)
        return user

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)
        instance.username = validated_data.get('username', instance.username)
        instance.email = validated_data.get('email', instance.email)
        instance.save()

        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        return instance
