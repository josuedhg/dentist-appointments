import calendar
import uuid
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    redirect_to_login,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import FormView
from rest_framework import permissions
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    RetrieveUpdateDestroyAPIView,
)

from .forms import (
    AppointmentForm,
    DentistAppointmentForm,
    PatientCreateForm,
    ProfileForm,
)
from .models import Appointment, DentistProfile, PatientProfile
from .serializers import (
    AppointmentSerializer,
    DoctorSerializer,
    PatientSerializer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_doctor(user):
    return user.is_authenticated and user.groups.filter(name="doctor").exists()


def is_patient(user):
    return user.is_authenticated and user.groups.filter(name="patient").exists()


def _must_change_password(user):
    return (
        DentistProfile.objects.filter(
            user=user, must_change_password=True
        ).exists()
        or PatientProfile.objects.filter(
            user=user, must_change_password=True
        ).exists()
    )


def _clear_password_change_flag(user):
    DentistProfile.objects.filter(user=user).update(must_change_password=False)
    PatientProfile.objects.filter(user=user).update(must_change_password=False)


def _doctor_only_if_needed(request):
    """Prevent dentist accounts from using the patient booking screens."""
    if is_doctor(request.user) and not is_patient(request.user):
        messages.error(request, "Dentist accounts cannot book patient appointments.")
        return redirect("doctor-dashboard")
    return None


# ---------------------------------------------------------------------------
# Registration and authentication
# ---------------------------------------------------------------------------
def patient_registration_info(request):
    """Patient accounts are created by their dentist."""
    return render(request, "appointments/patient_registration_info.html")


def patient_activate(request, token):
    """One-time link created by a dentist: log the patient in and ask them to
    choose a password.
    """
    profile = get_object_or_404(
        PatientProfile.objects.select_related("user"),
        login_token=token,
        user__is_active=True,
        user__groups__name="patient",
    )
    auth_login(
        request,
        profile.user,
        backend="django.contrib.auth.backends.ModelBackend",
    )
    profile.must_change_password = True
    profile.save(update_fields=["must_change_password"])
    messages.info(
        request,
        "Welcome! Choose a password to finish setting up your account.",
    )
    return redirect("password-setup")


class ForcedPasswordSetupView(FormView):
    """First password for invited patients and admin-created dentists."""

    form_class = SetPasswordForm
    template_name = "appointments/password_setup.html"
    success_url = reverse_lazy("dashboard")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not _must_change_password(request.user):
            return redirect("account")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        form.save()
        update_session_auth_hash(self.request, user)
        _clear_password_change_flag(user)
        # Invalidate any outstanding invitation link after it has been used.
        PatientProfile.objects.filter(user=user).update(login_token=uuid.uuid4())
        messages.success(self.request, "Your password has been set.")
        return super().form_valid(form)


def doctor_registration_info(request):
    """Dentist accounts are created by the site administrator."""
    return render(request, "appointments/doctor_registration_info.html")


class RoleAwareLoginView(LoginView):
    template_name = "appointments/login.html"
    redirect_authenticated_user = True


class DentistPasswordChangeView(PasswordChangeView):
    template_name = "appointments/password_change.html"
    success_url = reverse_lazy("dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["forced"] = _must_change_password(self.request.user)
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        _clear_password_change_flag(self.request.user)
        messages.success(self.request, "Your password has been updated.")
        return response


@login_required
def account(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request, "Your account information has been updated."
            )
            return redirect("account")
    else:
        form = ProfileForm(instance=request.user)

    return render(
        request,
        "appointments/account.html",
        {
            "form": form,
            "must_change_password": _must_change_password(request.user),
        },
    )


# ---------------------------------------------------------------------------
# Patient-facing pages
# ---------------------------------------------------------------------------
def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "appointments/home.html")


@login_required
def dashboard(request):
    if is_doctor(request.user):
        return redirect("doctor-dashboard")
    if is_patient(request.user):
        return redirect("patient-appointments")
    if request.user.is_staff:
        return redirect("/admin/")
    messages.info(
        request,
        "Your account has no role yet. Ask your dentist to create your "
        "patient account.",
    )
    return redirect("account")


@login_required
def patient_appointments(request):
    blocked = _doctor_only_if_needed(request)
    if blocked:
        return blocked
    appointments = (
        Appointment.objects.filter(patient=request.user)
        .select_related("doctor")
        .order_by("date", "time")
    )
    return render(
        request,
        "appointments/patient_appointments.html",
        {"appointments": appointments},
    )


@login_required
def book_appointment(request):
    blocked = _doctor_only_if_needed(request)
    if blocked:
        return blocked

    if request.method == "POST":
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = request.user
            appointment.save()
            messages.success(
                request,
                "Your appointment has been booked. Save the private link below "
                "to check it at any time.",
            )
            return redirect(appointment.get_absolute_url())
    else:
        form = AppointmentForm()

    return render(
        request,
        "appointments/book_appointment.html",
        {"form": form},
    )


@login_required
@require_POST
def cancel_appointment(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, patient=request.user)
    if appointment.status == Appointment.STATUS_SCHEDULED:
        appointment.status = Appointment.STATUS_CANCELLED
        appointment.save(update_fields=["status"])
        messages.success(request, "Your appointment has been cancelled.")
    else:
        messages.error(request, "Only scheduled appointments can be cancelled.")
    return redirect("patient-appointments")


def appointment_detail(request, token):
    """Public appointment page: no login, password, or email required."""
    appointment = get_object_or_404(
        Appointment.objects.select_related("patient", "doctor"),
        access_token=token,
    )
    return render(
        request,
        "appointments/appointment_detail.html",
        {"appointment": appointment},
    )


# ---------------------------------------------------------------------------
# Dentist-facing pages
# ---------------------------------------------------------------------------
@login_required
@user_passes_test(is_doctor, login_url="login")
def doctor_dashboard(request):
    today = timezone.localdate()
    month_param = request.GET.get("month", "")
    try:
        selected = date.fromisoformat(f"{month_param}-01")
    except ValueError:
        selected = today.replace(day=1)

    month_start = selected.replace(day=1)
    if month_start.month == 12:
        next_month_start = date(month_start.year + 1, 1, 1)
    else:
        next_month_start = date(month_start.year, month_start.month + 1, 1)
    month_end = next_month_start - timedelta(days=1)
    previous_month_start = (month_start - timedelta(days=1)).replace(day=1)

    try:
        selected_day = date.fromisoformat(request.GET.get("day", ""))
    except ValueError:
        selected_day = None
    if selected_day is None or not (month_start <= selected_day <= month_end):
        selected_day = today if month_start <= today <= month_end else month_start

    month_appointments = list(
        Appointment.objects.filter(
            doctor=request.user,
            date__range=(month_start, month_end),
        )
        .select_related("patient")
        .order_by("date", "time")
    )
    by_day = {}
    for appointment in month_appointments:
        by_day.setdefault(appointment.date, []).append(appointment)

    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(
        month_start.year, month_start.month
    ):
        weeks.append(
            [
                {
                    "date": day,
                    "in_month": day.month == month_start.month,
                    "is_selected": day == selected_day,
                    "appointments": by_day.get(day, []),
                }
                for day in week
            ]
        )

    day_appointments = by_day.get(selected_day, [])

    other = (
        Appointment.objects.filter(doctor=request.user)
        .exclude(status=Appointment.STATUS_SCHEDULED, date__gte=today)
        .select_related("patient")
        .order_by("-date", "-time")
    )
    return render(
        request,
        "appointments/doctor_dashboard.html",
        {
            "weeks": weeks,
            "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "month_start": month_start,
            "month_end": month_end,
            "selected_day": selected_day,
            "day_appointments": day_appointments,
            "previous_month": previous_month_start,
            "next_month": next_month_start,
            "today": today,
            "status_choices": Appointment.STATUS_CHOICES,
        },
    )


@login_required
@user_passes_test(is_doctor, login_url="login")
@require_POST
def update_appointment_status(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, doctor=request.user)
    new_status = request.POST.get("status")
    if new_status not in dict(Appointment.STATUS_CHOICES):
        messages.error(request, "Invalid appointment status.")
    else:
        appointment.status = new_status
        appointment.save(update_fields=["status"])
        messages.success(
            request, f"Appointment #{appointment.pk} marked as {new_status}."
        )
    return redirect("doctor-dashboard")


# ---------------------------------------------------------------------------
# Dentist: patient accounts and appointments
# ---------------------------------------------------------------------------
@login_required
@user_passes_test(is_doctor, login_url="login")
def doctor_patients(request):
    patients = (
        User.objects.filter(groups__name="patient", is_active=True)
        .select_related("patient_profile")
        .order_by("first_name", "last_name", "username")
    )
    return render(
        request,
        "appointments/doctor_patients.html",
        {"patients": patients},
    )


@login_required
@user_passes_test(is_doctor, login_url="login")
def doctor_patient_create(request):
    if request.method == "POST":
        form = PatientCreateForm(request.POST)
        if form.is_valid():
            patient = form.save()
            PatientProfile.objects.update_or_create(
                user=patient, defaults={"must_change_password": True}
            )
            messages.success(
                request,
                "Patient added. Share the login link below so they can "
                "choose a password.",
            )
            return redirect("doctor-patient-detail", pk=patient.pk)
    else:
        form = PatientCreateForm()

    return render(
        request,
        "appointments/doctor_patient_form.html",
        {"form": form},
    )


@login_required
@user_passes_test(is_doctor, login_url="login")
def doctor_patient_detail(request, pk):
    patient = get_object_or_404(
        User.objects.filter(groups__name="patient"), pk=pk
    )
    profile, _ = PatientProfile.objects.get_or_create(user=patient)
    appointments = (
        patient.patient_appointments.select_related("doctor")
        .order_by("-date", "-time")
    )
    activation_url = None
    if profile.must_change_password:
        activation_url = request.build_absolute_uri(
            reverse("patient-activate", args=[profile.login_token])
        )
    return render(
        request,
        "appointments/doctor_patient_detail.html",
        {
            "patient": patient,
            "profile": profile,
            "appointments": appointments,
            "activation_url": activation_url,
        },
    )


@login_required
@user_passes_test(is_doctor, login_url="login")
@require_POST
def doctor_patient_reset_password(request, pk):
    patient = get_object_or_404(
        User.objects.filter(groups__name="patient"), pk=pk
    )
    patient.set_unusable_password()
    patient.save(update_fields=["password"])
    PatientProfile.objects.update_or_create(
        user=patient,
        defaults={
            "must_change_password": True,
            "login_token": uuid.uuid4(),
        },
    )
    messages.success(
        request,
        "Password reset. Share the new login link with the patient.",
    )
    return redirect("doctor-patient-detail", pk=patient.pk)


@login_required
@user_passes_test(is_doctor, login_url="login")
def doctor_appointment_create(request):
    initial = {}
    patient_id = request.GET.get("patient")
    if patient_id:
        try:
            initial["patient"] = User.objects.get(
                pk=patient_id, groups__name="patient"
            )
        except (User.DoesNotExist, TypeError, ValueError):
            pass

    if request.method == "POST":
        form = DentistAppointmentForm(request.POST, doctor=request.user)
        if form.is_valid():
            appointment = form.save()
            messages.success(request, "Appointment added to your schedule.")
            return redirect(
                f"{reverse('doctor-dashboard')}"
                f"?month={appointment.date:%Y-%m}"
                f"&day={appointment.date:%Y-%m-%d}"
            )
    else:
        form = DentistAppointmentForm(initial=initial, doctor=request.user)

    return render(
        request,
        "appointments/doctor_appointment_form.html",
        {"form": form},
    )


# ---------------------------------------------------------------------------
# REST API (kept for programmatic clients)
# ---------------------------------------------------------------------------
class DoctorCreateView(CreateAPIView):
    model = User
    serializer_class = DoctorSerializer
    permission_classes = (permissions.IsAdminUser,)


class PatientCreateView(CreateAPIView):
    model = User
    serializer_class = PatientSerializer


class AppointmentListView(ListAPIView):
    model = Appointment
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer
    permission_classes = (permissions.IsAuthenticated,)


class AppointmentCreateView(CreateAPIView):
    model = Appointment
    serializer_class = AppointmentSerializer
    permission_classes = (permissions.IsAuthenticated,)


class AppointmentRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    queryset = Appointment.objects.all()
    model = Appointment
    serializer_class = AppointmentSerializer
    permission_classes = (permissions.IsAuthenticated,)
