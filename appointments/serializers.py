from rest_framework import serializers
from django.contrib.auth.models import User, Group, Permission
from .models import Appointment


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'username', 'email',
                  'password')

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        doctor_group, created = Group.objects.get_or_create(name='doctor')
        if created:
            doctor_group.permissions.set([
                Permission.objects.get(codename='change_appointment'),
                Permission.objects.get(codename='delete_appointment'),
                Permission.objects.get(codename='view_appointment')
            ])
        doctor_group.user_set.add(user)
        return user


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'first_name', 'last_name', 'username', 'email',
                  'password')

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        patient_group, created = Group.objects.get_or_create(name='patient')
        if created:
            patient_group.permissions.set([Permission.objects.get(
                codename='add_appointment')])
        patient_group.user_set.add(user)
        return user


class AppointmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Appointment
        fields = ('id', 'patient', 'doctor', 'date', 'time')
