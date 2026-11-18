from django.contrib.auth.models import Group, Permission, User
from rest_framework import serializers

from .models import Appointment, DentistProfile


def add_user_to_group(user, group_name, permission_codenames=()):
    """Add a user to a role group and grant the group its permissions."""
    group, _ = Group.objects.get_or_create(name=group_name)
    if permission_codenames:
        group.permissions.add(
            *Permission.objects.filter(codename__in=permission_codenames)
        )
    group.user_set.add(user)


class DoctorSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "username",
            "email",
            "password",
        )

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        add_user_to_group(
            user,
            "doctor",
            ("change_appointment", "delete_appointment", "view_appointment"),
        )
        DentistProfile.objects.update_or_create(
            user=user, defaults={"must_change_password": True}
        )
        return user


class PatientSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            "id",
            "first_name",
            "last_name",
            "username",
            "email",
            "password",
        )

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        add_user_to_group(user, "patient", ("add_appointment",))
        return user


class AppointmentSerializer(serializers.ModelSerializer):
    access_token = serializers.UUIDField(read_only=True)

    class Meta:
        model = Appointment
        fields = (
            "id",
            "patient",
            "doctor",
            "date",
            "time",
            "notes",
            "status",
            "access_token",
        )
        read_only_fields = ("status", "access_token")

    def validate(self, attrs):
        doctor = attrs.get("doctor", getattr(self.instance, "doctor", None))
        date = attrs.get("date", getattr(self.instance, "date", None))
        time = attrs.get("time", getattr(self.instance, "time", None))
        if doctor and date and time:
            clash = (
                Appointment.objects.filter(
                    doctor=doctor,
                    date=date,
                    time=time,
                    status=Appointment.STATUS_SCHEDULED,
                )
                .exclude(pk=getattr(self.instance, "pk", None))
                .exists()
            )
            if clash:
                raise serializers.ValidationError(
                    {
                        "time": (
                            "This dentist already has an appointment at that "
                            "date and time."
                        )
                    }
                )
        return attrs
