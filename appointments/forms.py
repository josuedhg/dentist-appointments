from django import forms
from django.contrib.auth.models import Group, User
from django.utils import timezone

from .models import Appointment


def add_user_to_group(user, group_name):
    """Add a user to a role group, creating the group when necessary."""
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


class PatientCreateForm(forms.ModelForm):
    """Dentist-facing form for creating a patient account.

    No password is collected here: the dentist gets a one-time link that logs
    the patient in and asks them to choose their own password.
    """

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")
        help_texts = {
            "username": "The patient uses this to log in after setting a password.",
            "email": "Optional.",
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_unusable_password()
        if commit:
            user.save()
            add_user_to_group(user, "patient")
        return user


class ProfileForm(forms.ModelForm):
    """Let any logged-in user update their own account information."""

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")
        help_texts = {
            "email": "Optional.",
            "username": "You use this to log in.",
        }


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ("doctor", "date", "time", "notes")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Reason for the visit (optional)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doctor"].queryset = User.objects.filter(
            groups__name="doctor", is_active=True
        ).order_by("first_name", "last_name", "username")
        self.fields["doctor"].empty_label = "Select a dentist"
        # Keep the browser date picker from offering past dates.
        self.fields["date"].widget.attrs["min"] = timezone.localdate().isoformat()


class DentistAppointmentForm(forms.ModelForm):
    """Appointment form used by a dentist for one of their patients."""

    class Meta:
        model = Appointment
        fields = ("patient", "date", "time", "notes")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Reason for the visit (optional)",
                }
            ),
        }

    def __init__(self, *args, doctor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.doctor = doctor
        if doctor is not None:
            # Let the model's double-booking validation see the dentist.
            self.instance.doctor = doctor
        self.fields["patient"].queryset = User.objects.filter(
            groups__name="patient", is_active=True
        ).order_by("first_name", "last_name", "username")
        self.fields["patient"].empty_label = "Select a patient"
        self.fields["date"].widget.attrs["min"] = timezone.localdate().isoformat()

    def save(self, commit=True):
        appointment = super().save(commit=False)
        if self.doctor is not None:
            appointment.doctor = self.doctor
        if commit:
            appointment.save()
        return appointment
