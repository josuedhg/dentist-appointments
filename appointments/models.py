import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


def validate_not_past(value):
    """Reject appointment dates that are before today."""
    if value and value < timezone.localdate():
        raise ValidationError("The appointment date cannot be in the past.")


class Appointment(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_appointments",
        limit_choices_to=Q(groups__name="patient"),
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_appointments",
        limit_choices_to=Q(groups__name="doctor"),
    )
    date = models.DateField(validators=[validate_not_past])
    time = models.TimeField()
    notes = models.TextField(
        blank=True,
        help_text="Optional details about the visit (for example: toothache).",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
    )
    # Unguessable token used by the public "view my appointment" URL.
    access_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["date", "time"]
        indexes = [
            models.Index(fields=["doctor", "date"]),
            models.Index(fields=["patient", "date"]),
        ]

    def __str__(self):
        return (
            f"{self.patient_name} with {self.doctor_name} "
            f"on {self.date} at {self.time:%H:%M}"
        )

    @property
    def patient_name(self):
        return self.patient.get_full_name() or self.patient.username

    @property
    def doctor_name(self):
        full_name = self.doctor.get_full_name()
        return f"Dr. {full_name}" if full_name else f"Dr. {self.doctor.username}"

    @property
    def short_reference(self):
        return str(self.access_token).split("-")[0].upper()

    def get_absolute_url(self):
        return reverse("appointment-detail", kwargs={"token": self.access_token})

    def clean(self):
        super().clean()
        # A dentist cannot have two active appointments in the same slot.
        if self.doctor_id and self.date and self.time:
            clash = (
                Appointment.objects.filter(
                    doctor_id=self.doctor_id,
                    date=self.date,
                    time=self.time,
                    status=self.STATUS_SCHEDULED,
                )
                .exclude(pk=self.pk)
                .exists()
            )
            if clash:
                raise ValidationError(
                    {
                        "time": (
                            "This dentist already has an appointment at that "
                            "date and time. Please choose another slot."
                        )
                    }
                )


class Dentist(User):
    """Proxy model used to give dentists their own section in the admin."""

    class Meta:
        proxy = True
        verbose_name = "dentist"
        verbose_name_plural = "dentists"

    def __str__(self):
        return self.get_full_name() or self.username


class DentistProfile(models.Model):
    """Dentist-only account state that does not belong on the User model."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dentist_profile",
    )
    must_change_password = models.BooleanField(
        default=True,
        help_text=(
            "When enabled, the dentist is forced to choose a new password "
            "the next time they log in."
        ),
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f"Profile for {self.user}"


class PatientProfile(models.Model):
    """Patient account state: forced password setup and invitation links."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    must_change_password = models.BooleanField(
        default=True,
        help_text=(
            "When enabled, the patient is forced to choose a new password "
            "the next time they log in."
        ),
    )
    login_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text=(
            "Used in the one-time link that logs a patient in and asks them "
            "to choose a password."
        ),
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return f"Profile for {self.user}"
