"""URL configuration for the dentist project's appointments app."""
from django.urls import path

from . import views

urlpatterns = [
    # Public / shared pages
    path("", views.home, name="home"),
    path("login/", views.RoleAwareLoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(next_page="home"), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # Registration
    path(
        "register/patient/",
        views.patient_registration_info,
        name="patient-register",
    ),
    path(
        "register/doctor/",
        views.doctor_registration_info,
        name="doctor-register",
    ),
    path(
        "activate/<uuid:token>/",
        views.patient_activate,
        name="patient-activate",
    ),
    # Account
    path("account/", views.account, name="account"),
    path(
        "account/password/",
        views.DentistPasswordChangeView.as_view(),
        name="password-change",
    ),
    path(
        "account/set-password/",
        views.ForcedPasswordSetupView.as_view(),
        name="password-setup",
    ),
    # Patient pages
    path(
        "appointments/",
        views.patient_appointments,
        name="patient-appointments",
    ),
    path(
        "appointments/book/",
        views.book_appointment,
        name="book-appointment",
    ),
    path(
        "appointments/<int:pk>/cancel/",
        views.cancel_appointment,
        name="cancel-appointment",
    ),
    # Dentist pages
    path("doctor/", views.doctor_dashboard, name="doctor-dashboard"),
    path(
        "doctor/patients/",
        views.doctor_patients,
        name="doctor-patients",
    ),
    path(
        "doctor/patients/new/",
        views.doctor_patient_create,
        name="doctor-patient-create",
    ),
    path(
        "doctor/patients/<int:pk>/",
        views.doctor_patient_detail,
        name="doctor-patient-detail",
    ),
    path(
        "doctor/patients/<int:pk>/reset-password/",
        views.doctor_patient_reset_password,
        name="doctor-patient-reset-password",
    ),
    path(
        "doctor/appointments/new/",
        views.doctor_appointment_create,
        name="doctor-appointment-create",
    ),
    path(
        "doctor/appointments/<int:pk>/status/",
        views.update_appointment_status,
        name="update-appointment-status",
    ),
    # Public appointment detail (unguessable token, no login needed)
    path(
        "appointment/<uuid:token>/",
        views.appointment_detail,
        name="appointment-detail",
    ),
    # REST API
    path(
        "api/patient/create",
        views.PatientCreateView.as_view(),
        name="patient-create",
    ),
    path(
        "api/doctor/create",
        views.DoctorCreateView.as_view(),
        name="doctor-create",
    ),
    path(
        "api/appointment/",
        views.AppointmentListView.as_view(),
        name="appointment-list",
    ),
    path(
        "api/appointment/<int:pk>/",
        views.AppointmentRetrieveUpdateDestroyView.as_view(),
        name="appointment-detail-api",
    ),
    path(
        "api/appointment/create",
        views.AppointmentCreateView.as_view(),
        name="appointment-create",
    ),
]
