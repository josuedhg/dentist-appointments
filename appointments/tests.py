from datetime import time, timedelta
import json

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, DentistProfile, PatientProfile
from .serializers import AppointmentSerializer


def make_user(username, group_name, **extra):
    user = User.objects.create_user(username=username, password="test-pass-123", **extra)
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    return user


def make_dentist(username, must_change_password=False, **extra):
    user = make_user(username, "doctor", **extra)
    DentistProfile.objects.update_or_create(
        user=user, defaults={"must_change_password": must_change_password}
    )
    return user


class AppointmentModelTest(TestCase):
    def setUp(self):
        self.patient = make_user("patient", "patient", first_name="Alice")
        self.doctor = make_user("doctor", "doctor", first_name="Bob")

    def test_create_appointment_gets_access_token(self):
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=timezone.localdate(),
            time=time(10, 0),
        )
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertIsNotNone(appointment.access_token)
        self.assertIn(str(appointment.access_token), appointment.get_absolute_url())

    def test_past_date_is_rejected_by_validation(self):
        appointment = Appointment(
            patient=self.patient,
            doctor=self.doctor,
            date=timezone.localdate() - timedelta(days=1),
            time=time(10, 0),
        )
        with self.assertRaises(ValidationError):
            appointment.full_clean()

    def test_dentist_cannot_have_two_active_appointments_in_same_slot(self):
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=timezone.localdate(),
            time=time(10, 0),
        )
        duplicate = Appointment(
            patient=self.patient,
            doctor=self.doctor,
            date=timezone.localdate(),
            time=time(10, 0),
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_cancelled_appointment_frees_the_slot(self):
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=timezone.localdate(),
            time=time(10, 0),
            status=Appointment.STATUS_CANCELLED,
        )
        replacement = Appointment(
            patient=self.patient,
            doctor=self.doctor,
            date=timezone.localdate(),
            time=time(10, 0),
        )
        replacement.full_clean()  # should not raise


class AppointmentSerializerTest(TestCase):
    def test_appointment_serializer(self):
        patient = make_user("patient", "patient")
        doctor = make_user("doctor", "doctor")
        appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            date=timezone.localdate(),
            time=time(10, 0),
        )
        serializer = AppointmentSerializer(appointment)
        self.assertEqual(serializer.data["patient"], patient.pk)
        self.assertEqual(serializer.data["doctor"], doctor.pk)
        self.assertEqual(serializer.data["date"], str(timezone.localdate()))
        self.assertEqual(serializer.data["time"], "10:00:00")
        self.assertIn("access_token", serializer.data)


class ApiTests(TestCase):
    def test_patient_create_api_sets_group_and_hides_password(self):
        response = self.client.post(
            reverse("patient-create"),
            data=json.dumps(
                {
                    "first_name": "Api",
                    "last_name": "Alice",
                    "username": "apialice",
                    "email": "api@example.com",
                    "password": "Str0ngPass!23",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="apialice")
        self.assertTrue(user.groups.filter(name="patient").exists())
        self.assertTrue(user.check_password("Str0ngPass!23"))
        self.assertNotIn("password", response.json())

    def test_doctor_create_api_requires_admin(self):
        patient = make_user("alice", "patient")
        self.client.force_login(patient)
        response = self.client.post(
            reverse("doctor-create"),
            data=json.dumps(
                {
                    "first_name": "Api",
                    "last_name": "Doctor",
                    "username": "apidoctor",
                    "email": "doctor@example.com",
                    "password": "Str0ngPass!23",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="apidoctor").exists())

    def test_admin_can_create_doctor_api_with_forced_password_change(self):
        admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="admin-pass-123"
        )
        self.client.force_login(admin)
        response = self.client.post(
            reverse("doctor-create"),
            data=json.dumps(
                {
                    "first_name": "Api",
                    "last_name": "Doctor",
                    "username": "apidoctor",
                    "email": "doctor@example.com",
                    "password": "Str0ngPass!23",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="apidoctor")
        self.assertTrue(user.groups.filter(name="doctor").exists())
        self.assertTrue(DentistProfile.objects.get(user=user).must_change_password)

    def test_appointment_create_api_returns_public_token(self):
        patient = make_user("alice", "patient")
        doctor = make_user("drbob", "doctor")
        self.client.force_login(patient)
        response = self.client.post(
            reverse("appointment-create"),
            data=json.dumps(
                {
                    "patient": patient.pk,
                    "doctor": doctor.pk,
                    "date": timezone.localdate().isoformat(),
                    "time": "10:00",
                    "notes": "Api booking",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("access_token", response.json())
        self.assertEqual(Appointment.objects.count(), 1)


class RegistrationTests(TestCase):
    def test_patient_cannot_self_register(self):
        response = self.client.get(reverse("patient-register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "created by the dentist")

        response = self.client.post(
            reverse("patient-register"),
            {
                "username": "alice",
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="alice").exists())

    def test_doctor_cannot_self_register(self):
        response = self.client.get(reverse("doctor-register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "created by the clinic administrator")

        response = self.client.post(
            reverse("doctor-register"),
            {
                "username": "drbob",
                "first_name": "Bob",
                "last_name": "Jones",
                "email": "bob@example.com",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="drbob").exists())

    def test_login_redirects_to_dashboard(self):
        make_user("alice", "patient")
        response = self.client.post(
            reverse("login"), {"username": "alice", "password": "test-pass-123"}
        )
        self.assertRedirects(
            response, reverse("dashboard"), fetch_redirect_response=False
        )


class PublicPageTests(TestCase):
    def test_home_page_renders(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Book a dental appointment")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log in")

    def test_registration_pages_render(self):
        cases = [
            ("patient-register", "created by the dentist"),
            ("doctor-register", "created by the clinic administrator"),
        ]
        for url_name, expected_text in cases:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_text)


class PatientFlowTests(TestCase):
    def setUp(self):
        self.patient = make_user(
            "alice", "patient", first_name="Alice", last_name="Smith"
        )
        self.doctor = make_user(
            "drbob", "doctor", first_name="Bob", last_name="Jones"
        )
        self.client.force_login(self.patient)

    def test_booking_page_renders(self):
        response = self.client.get(reverse("book-appointment"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm appointment")

    def test_patient_can_book_an_appointment(self):
        response = self.client.post(
            reverse("book-appointment"),
            {
                "doctor": self.doctor.pk,
                "date": timezone.localdate().isoformat(),
                "time": "10:00",
                "notes": "Toothache",
            },
        )
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.patient, self.patient)
        self.assertEqual(appointment.doctor, self.doctor)
        self.assertEqual(appointment.notes, "Toothache")
        self.assertRedirects(response, appointment.get_absolute_url())

    def test_double_booking_same_slot_is_rejected(self):
        payload = {
            "doctor": self.doctor.pk,
            "date": timezone.localdate().isoformat(),
            "time": "10:00",
            "notes": "",
        }
        self.client.post(reverse("book-appointment"), payload)
        response = self.client.post(reverse("book-appointment"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertContains(response, "already has an appointment")

    def test_patient_can_cancel_own_appointment(self):
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=timezone.localdate(),
            time=time(11, 0),
        )
        response = self.client.post(
            reverse("cancel-appointment", args=[appointment.pk])
        )
        self.assertRedirects(response, reverse("patient-appointments"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.STATUS_CANCELLED)

    def test_patient_cannot_open_dentist_dashboard(self):
        response = self.client.get(reverse("doctor-dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)


class PublicAppointmentTests(TestCase):
    def setUp(self):
        self.patient = make_user(
            "alice",
            "patient",
            first_name="Alice",
            last_name="Smith",
            email="secret@example.com",
        )
        self.doctor = make_user(
            "drbob",
            "doctor",
            first_name="Bob",
            last_name="Jones",
            email="dentist-secret@example.com",
        )
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=timezone.localdate(),
            time=time(10, 0),
            notes="Regular check-up",
        )

    def test_public_link_works_without_login(self):
        response = self.client.get(self.appointment.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Smith")
        self.assertContains(response, "Dr. Bob Jones")
        self.assertContains(response, "Regular check-up")

    def test_public_link_does_not_expose_emails(self):
        response = self.client.get(self.appointment.get_absolute_url())
        self.assertNotContains(response, "secret@example.com")
        self.assertNotContains(response, "dentist-secret@example.com")

    def test_unknown_token_returns_404(self):
        response = self.client.get(
            reverse(
                "appointment-detail",
                kwargs={"token": "00000000-0000-0000-0000-000000000000"},
            )
        )
        self.assertEqual(response.status_code, 404)


class DoctorFlowTests(TestCase):
    def setUp(self):
        self.patient = make_user(
            "alice", "patient", first_name="Alice", last_name="Smith"
        )
        self.doctor = make_user(
            "drbob", "doctor", first_name="Bob", last_name="Jones"
        )
        self.other_doctor = make_user(
            "drjane", "doctor", first_name="Jane", last_name="Doe"
        )
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=timezone.localdate(),
            time=time(10, 0),
        )

    def test_dentist_dashboard_lists_only_own_appointments(self):
        other_patient = make_user(
            "bob", "patient", first_name="Bob", last_name="Brown"
        )
        Appointment.objects.create(
            patient=other_patient,
            doctor=self.other_doctor,
            date=timezone.localdate(),
            time=time(12, 0),
        )
        self.client.force_login(self.doctor)
        response = self.client.get(reverse("doctor-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "calendar-grid")
        self.assertContains(response, "Alice Smith")
        self.assertNotContains(response, "Bob Brown")

    def test_dentist_dashboard_grid_shows_only_appointment_counts(self):
        other_day = (
            timezone.localdate().replace(day=1)
            if timezone.localdate().day != 1
            else timezone.localdate().replace(day=2)
        )
        other_patient = make_user(
            "bob", "patient", first_name="Bob", last_name="Brown"
        )
        Appointment.objects.create(
            patient=other_patient,
            doctor=self.doctor,
            date=other_day,
            time=time(11, 0),
        )
        self.client.force_login(self.doctor)

        # Today is selected, so only the side panel shows patient names.
        response = self.client.get(reverse("doctor-dashboard"))
        self.assertContains(response, 'class="appt-count')
        self.assertContains(response, "Alice Smith")
        self.assertNotContains(response, "Bob Brown")

        # Clicking the other day loads that day in the side panel.
        response = self.client.get(
            reverse("doctor-dashboard"),
            {"day": other_day.isoformat()},
        )
        self.assertContains(response, "Bob Brown")
        self.assertNotContains(response, "Alice Smith")

    def test_dentist_dashboard_shows_current_month_grid(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse("doctor-dashboard"))
        self.assertContains(response, "My schedule")
        self.assertContains(response, timezone.localdate().strftime("%B %Y"))
        self.assertContains(response, "calendar-weekdays")
        self.assertContains(response, "This month")

    def test_dentist_dashboard_navigates_between_months(self):
        next_patient = make_user(
            "nextpatient", "patient", first_name="Next", last_name="Month"
        )
        next_month_start = (timezone.localdate().replace(day=1) + timedelta(days=32)).replace(
            day=1
        )
        Appointment.objects.create(
            patient=next_patient,
            doctor=self.doctor,
            date=next_month_start,
            time=time(9, 0),
        )
        self.client.force_login(self.doctor)

        response = self.client.get(reverse("doctor-dashboard"))
        self.assertNotContains(response, "Next Month")

        response = self.client.get(
            reverse("doctor-dashboard"),
            {"month": next_month_start.strftime("%Y-%m")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Next Month")
        self.assertContains(response, next_month_start.strftime("%B %Y"))

    def test_dentist_dashboard_side_panel_shows_selected_day(self):
        selected_day = (
            timezone.localdate().replace(day=2)
            if timezone.localdate().day == 1
            else timezone.localdate().replace(day=1)
        )
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            date=selected_day,
            time=time(11, 0),
        )
        self.client.force_login(self.doctor)

        response = self.client.get(
            reverse("doctor-dashboard"),
            {"day": selected_day.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_day"], selected_day)
        self.assertEqual(
            [item.pk for item in response.context["day_appointments"]],
            [appointment.pk],
        )
        self.assertNotIn(self.appointment, response.context["day_appointments"])
        self.assertContains(response, selected_day.strftime("%A"))
        self.assertContains(
            response,
            f"{selected_day.strftime('%B')} {selected_day.day}, {selected_day.year}",
        )

    def test_dentist_dashboard_ignores_day_outside_displayed_month(self):
        self.client.force_login(self.doctor)
        response = self.client.get(
            reverse("doctor-dashboard"),
            {"day": "1999-01-01"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_day"], timezone.localdate()
        )

    def test_dentist_can_update_appointment_status(self):
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse("update-appointment-status", args=[self.appointment.pk]),
            {"status": Appointment.STATUS_COMPLETED},
        )
        self.assertRedirects(response, reverse("doctor-dashboard"))
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.STATUS_COMPLETED)

    def test_dentist_cannot_update_another_dentists_appointment(self):
        self.client.force_login(self.other_doctor)
        response = self.client.post(
            reverse("update-appointment-status", args=[self.appointment.pk]),
            {"status": Appointment.STATUS_COMPLETED},
        )
        self.assertEqual(response.status_code, 404)

    def test_dentist_cannot_book_as_patient(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse("book-appointment"))
        self.assertRedirects(response, reverse("doctor-dashboard"))


class DentistAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="admin-pass-123"
        )
        self.client.force_login(self.admin)

    def test_admin_can_create_dentist_with_temporary_password(self):
        response = self.client.post(
            reverse("admin:appointments_dentist_add"),
            {
                "username": "drbob",
                "first_name": "Bob",
                "last_name": "Jones",
                "email": "bob@example.com",
                "password1": "Str0ngPass!23",
                "password2": "Str0ngPass!23",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="drbob")
        self.assertTrue(user.groups.filter(name="doctor").exists())
        self.assertTrue(user.check_password("Str0ngPass!23"))
        self.assertTrue(DentistProfile.objects.get(user=user).must_change_password)

    def test_dentist_admin_lists_only_dentists(self):
        make_user("alice", "patient")
        make_dentist("drbob")
        response = self.client.get(reverse("admin:appointments_dentist_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "drbob")
        self.assertNotContains(response, "alice")

    def test_admin_password_reset_forces_change_on_next_login(self):
        dentist = make_dentist("drbob", must_change_password=False)
        response = self.client.post(
            f"/admin/appointments/dentist/{dentist.pk}/password/",
            {
                "password1": "NewTempPass!23",
                "password2": "NewTempPass!23",
            },
        )
        self.assertEqual(response.status_code, 302)
        dentist.refresh_from_db()
        self.assertTrue(dentist.check_password("NewTempPass!23"))
        self.assertTrue(
            DentistProfile.objects.get(user=dentist).must_change_password
        )

    def test_admin_can_open_dentist_change_form(self):
        dentist = make_dentist("drbob", first_name="Bob", last_name="Jones")
        response = self.client.get(
            reverse("admin:appointments_dentist_change", args=[dentist.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Personal info")

    def test_dentist_change_form_does_not_expose_groups(self):
        from .admin import DentistChangeForm

        self.assertNotIn("groups", DentistChangeForm.base_fields)


class ForcedPasswordChangeTests(TestCase):
    def test_flagged_dentist_is_sent_to_password_change(self):
        dentist = make_dentist("drbob", must_change_password=True)
        self.client.force_login(dentist)

        response = self.client.get(reverse("doctor-dashboard"))
        self.assertRedirects(response, reverse("password-change"))

        response = self.client.get(reverse("account"))
        self.assertRedirects(response, reverse("password-change"))

    def test_flagged_dentist_can_still_log_out(self):
        dentist = make_dentist("drbob", must_change_password=True)
        self.client.force_login(dentist)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("home"))

    def test_dentist_changes_password_and_flag_is_cleared(self):
        dentist = make_dentist("drbob", must_change_password=True)
        self.client.force_login(dentist)

        response = self.client.post(
            reverse("password-change"),
            {
                "old_password": "test-pass-123",
                "new_password1": "NewStr0ngPass!23",
                "new_password2": "NewStr0ngPass!23",
            },
        )
        self.assertRedirects(
            response, reverse("dashboard"), fetch_redirect_response=False
        )

        dentist.refresh_from_db()
        self.assertTrue(dentist.check_password("NewStr0ngPass!23"))
        self.assertFalse(
            DentistProfile.objects.get(user=dentist).must_change_password
        )
        self.assertEqual(
            self.client.get(reverse("doctor-dashboard")).status_code, 200
        )

    def test_dentist_without_flag_can_use_the_site(self):
        dentist = make_dentist("drbob", must_change_password=False)
        self.client.force_login(dentist)
        self.assertEqual(
            self.client.get(reverse("doctor-dashboard")).status_code, 200
        )

    def test_dentist_login_without_forced_change_reaches_schedule(self):
        make_dentist("drbob", must_change_password=False)
        response = self.client.post(
            reverse("login"),
            {"username": "drbob", "password": "test-pass-123"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.request["PATH_INFO"], reverse("doctor-dashboard")
        )
        self.assertContains(response, "My schedule")

    def test_home_redirects_logged_in_dentist_to_schedule(self):
        dentist = make_dentist("drbob", must_change_password=False)
        self.client.force_login(dentist)

        response = self.client.get(reverse("home"))
        self.assertRedirects(
            response, reverse("dashboard"), fetch_redirect_response=False
        )

        response = self.client.get(reverse("home"), follow=True)
        self.assertEqual(response.request["PATH_INFO"], reverse("doctor-dashboard"))

    def test_home_redirects_logged_in_patient_to_appointments(self):
        patient = make_user("alice", "patient")
        self.client.force_login(patient)

        response = self.client.get(reverse("home"), follow=True)
        self.assertEqual(
            response.request["PATH_INFO"], reverse("patient-appointments")
        )


class AccountTests(TestCase):
    def test_dentist_can_update_own_information(self):
        dentist = make_dentist(
            "drbob",
            must_change_password=False,
            first_name="Bob",
            last_name="Jones",
            email="bob@example.com",
        )
        self.client.force_login(dentist)

        response = self.client.post(
            reverse("account"),
            {
                "username": "drbob",
                "first_name": "Robert",
                "last_name": "Jones",
                "email": "robert@example.com",
            },
        )
        self.assertRedirects(response, reverse("account"))

        dentist.refresh_from_db()
        self.assertEqual(dentist.first_name, "Robert")
        self.assertEqual(dentist.email, "robert@example.com")

    def test_patient_can_update_own_information(self):
        patient = make_user("alice", "patient", first_name="Alice")
        self.client.force_login(patient)

        response = self.client.post(
            reverse("account"),
            {
                "username": "alice",
                "first_name": "Alicia",
                "last_name": "Smith",
                "email": "",
            },
        )
        self.assertRedirects(response, reverse("account"))

        patient.refresh_from_db()
        self.assertEqual(patient.first_name, "Alicia")
        self.assertEqual(patient.last_name, "Smith")

    def test_account_page_renders(self):
        patient = make_user("alice", "patient")
        self.client.force_login(patient)
        response = self.client.get(reverse("account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your information")
        self.assertContains(response, reverse("password-change"))


class DentistPatientManagementTests(TestCase):
    def setUp(self):
        self.doctor = make_dentist("drbob", first_name="Bob", last_name="Jones")
        self.patient = make_user(
            "alice", "patient", first_name="Alice", last_name="Smith"
        )
        self.patient_profile, _ = PatientProfile.objects.get_or_create(
            user=self.patient, defaults={"must_change_password": False}
        )

    def test_dentist_can_view_patients_list(self):
        self.client.force_login(self.doctor)
        response = self.client.get(reverse("doctor-patients"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Smith")
        self.assertContains(response, "alice")
        self.assertContains(response, reverse("doctor-patient-create"))

    def test_non_dentist_cannot_access_doctor_patients(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse("doctor-patients"))
        self.assertEqual(response.status_code, 302)

    def test_dentist_registers_patient_and_creates_activation_link(self):
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse("doctor-patient-create"),
            {
                "username": "charlie",
                "first_name": "Charlie",
                "last_name": "Brown",
                "email": "charlie@example.com",
            },
        )
        charlie = User.objects.get(username="charlie")
        self.assertTrue(charlie.groups.filter(name="patient").exists())
        self.assertFalse(charlie.has_usable_password())
        self.assertRedirects(
            response, reverse("doctor-patient-detail", args=[charlie.pk])
        )

        profile = PatientProfile.objects.get(user=charlie)
        self.assertTrue(profile.must_change_password)
        self.assertIsNotNone(profile.login_token)

        # Dentist visits the detail page and sees the activation link
        detail_resp = self.client.get(
            reverse("doctor-patient-detail", args=[charlie.pk])
        )
        self.assertEqual(detail_resp.status_code, 200)
        expected_link = reverse("patient-activate", args=[profile.login_token])
        self.assertContains(detail_resp, expected_link)
        self.assertContains(detail_resp, "Password pending")

    def test_patient_activation_link_logs_user_in_and_forces_password_setup(self):
        # Create invited patient
        charlie = User.objects.create_user(username="charlie", email="charlie@example.com")
        charlie.set_unusable_password()
        charlie.save()
        group, _ = Group.objects.get_or_create(name="patient")
        charlie.groups.add(group)
        profile = PatientProfile.objects.create(
            user=charlie, must_change_password=True
        )

        # Unauthenticated client visits activation URL
        activate_url = reverse("patient-activate", args=[profile.login_token])
        response = self.client.get(activate_url)
        self.assertRedirects(response, reverse("password-setup"))

        # Verify client is now logged in as charlie
        self.assertEqual(int(self.client.session["_auth_user_id"]), charlie.pk)

        # Verify middleware restricts charlie to password-setup
        blocked_resp = self.client.get(reverse("patient-appointments"))
        self.assertRedirects(blocked_resp, reverse("password-setup"))

        # Patient submits new password on password-setup
        post_resp = self.client.post(
            reverse("password-setup"),
            {
                "new_password1": "Ch4rlie!Secure2026",
                "new_password2": "Ch4rlie!Secure2026",
            },
        )
        self.assertRedirects(
            post_resp, reverse("dashboard"), fetch_redirect_response=False
        )

        # Password is now set and flag cleared
        charlie.refresh_from_db()
        self.assertTrue(charlie.check_password("Ch4rlie!Secure2026"))
        profile.refresh_from_db()
        self.assertFalse(profile.must_change_password)

        # Charlie can now access patient appointments without being redirected
        appts_resp = self.client.get(reverse("patient-appointments"))
        self.assertEqual(appts_resp.status_code, 200)

        # Old activation link cannot be reused (token was rotated)
        old_token_resp = self.client.get(activate_url)
        self.assertEqual(old_token_resp.status_code, 404)

    def test_dentist_resets_patient_password(self):
        # Alice starts with an active password and must_change_password=False
        self.patient_profile.must_change_password = False
        self.patient_profile.save()
        old_token = self.patient_profile.login_token

        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse("doctor-patient-reset-password", args=[self.patient.pk])
        )
        self.assertRedirects(
            response, reverse("doctor-patient-detail", args=[self.patient.pk])
        )

        self.patient.refresh_from_db()
        self.assertFalse(self.patient.has_usable_password())

        self.patient_profile.refresh_from_db()
        self.assertTrue(self.patient_profile.must_change_password)
        self.assertNotEqual(self.patient_profile.login_token, old_token)

        # Dentist detail view now displays the new activation link
        detail_resp = self.client.get(
            reverse("doctor-patient-detail", args=[self.patient.pk])
        )
        new_link = reverse(
            "patient-activate", args=[self.patient_profile.login_token]
        )
        self.assertContains(detail_resp, new_link)

    def test_dentist_sets_appointment_for_patient(self):
        self.client.force_login(self.doctor)
        appt_date = timezone.localdate() + timedelta(days=2)

        # Test pre-selected patient GET
        get_resp = self.client.get(
            f"{reverse('doctor-appointment-create')}?patient={self.patient.pk}"
        )
        self.assertEqual(get_resp.status_code, 200)

        # Post appointment
        post_resp = self.client.post(
            reverse("doctor-appointment-create"),
            {
                "patient": self.patient.pk,
                "date": appt_date.isoformat(),
                "time": "14:30",
                "notes": "Follow-up checkup",
            },
        )
        expected_redirect = (
            f"{reverse('doctor-dashboard')}"
            f"?month={appt_date:%Y-%m}&day={appt_date:%Y-%m-%d}"
        )
        self.assertRedirects(post_resp, expected_redirect)

        appt = Appointment.objects.get(
            doctor=self.doctor, patient=self.patient, date=appt_date
        )
        self.assertEqual(appt.time, time(14, 30))
        self.assertEqual(appt.notes, "Follow-up checkup")

    def test_dentist_setting_appointment_prevents_double_booking(self):
        self.client.force_login(self.doctor)
        appt_date = timezone.localdate() + timedelta(days=3)
        Appointment.objects.create(
            doctor=self.doctor,
            patient=self.patient,
            date=appt_date,
            time=time(15, 0),
        )

        other_patient = make_user("bob", "patient")
        response = self.client.post(
            reverse("doctor-appointment-create"),
            {
                "patient": other_patient.pk,
                "date": appt_date.isoformat(),
                "time": "15:00",
                "notes": "Another visit",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "time",
            "This dentist already has an appointment at that date and time. Please choose another slot.",
        )
        self.assertEqual(
            Appointment.objects.filter(doctor=self.doctor, date=appt_date).count(),
            1,
        )
