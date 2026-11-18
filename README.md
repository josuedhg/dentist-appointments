# DentalCare Appointments

A small Django application for a dental practice.

Patients are registered by their dentist, who generates a private activation link.
Opening that link logs the patient in automatically and prompts them to choose a password.
Dentists can also reset a patient's password (which generates a new login link) and schedule
appointments on their behalf. Dentist accounts are created by the site administrator, who
assigns a temporary password; dentists choose their own password on first login.
Every appointment also has a private, unguessable public link that shows its details without
any login, password, or email.

## Features

- Dentist-managed patient registration with automated one-time login links and password setup.
- Password reset for patients by the dentist, generating fresh login/setup links.
- Appointment scheduling by dentists for their patients, with double-booking prevention.
- Admin-only dentist registration with a temporary password.
- Forced password change on first login (for both admin-created dentists and invited patients).
- Account page where any user can update their name, username, and email, and change their password.
- Patient self-service appointment booking with dentist, date, time, and optional notes.
- Double-booking protection per dentist/date/time slot.
- Patient dashboard with private appointment links and cancellation.
- Dentist monthly calendar grid (current month by default, responsive down to a
  vertical day list); each day shows its appointment count, and clicking a day
  opens that day's appointments in the side panel
  and status updates (scheduled, completed, cancelled).
- Public appointment URL: `/appointment/<uuid-token>/` — no account required.
- REST API kept for programmatic clients (dentist creation is admin-only).
- Django admin for appointments, dentists, and profiles.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.sample .env        # then edit SECRET_KEY / DEBUG / ALLOWED_HOSTS
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/.

To use the Django admin, create a superuser:

```bash
python manage.py createsuperuser
```

## Creating dentist accounts

1. Log in to `/admin/`.
2. Open **Appointments → Dentists → Add dentist**.
3. Enter the dentist's username, name, optional email, and a temporary password.
4. Give those login details to the dentist.
5. On their first login, the dentist is redirected to `/account/password/` and
   must choose a new password before using the rest of the site.

If you later reset a dentist's password from **Appointments → Dentists**, the
same forced-change flow is enabled again for their next login.

Dentists can later update their own name, username, and email at `/account/`,
and change their password at any time.

## Creating patient accounts and managing appointments

1. A dentist logs in and navigates to **Patients → Register patient** (`/doctor/patients/new/`).
2. The dentist enters the patient's username, name, and optional email.
3. Upon creation, the dentist is redirected to the patient's detail page (`/doctor/patients/<id>/`), which displays a private activation link (`/activate/<uuid-token>/`).
4. The dentist sends this link to the patient.
5. When the patient opens the link, they are automatically logged in and redirected to `/account/set-password/` to choose their password.
6. The dentist can reset a patient's password at any time from the patient detail page, which disables the existing password and generates a new activation link.
7. The dentist can schedule an appointment for any patient directly via `/doctor/appointments/new/` or from the patient's detail page.

## Main URLs

| URL | Description |
| --- | --- |
| `/` | Landing page |
| `/register/patient/` | Information page (patients are registered by dentists) |
| `/register/doctor/` | Information page (dentist accounts are admin-created) |
| `/activate/<token>/` | One-time patient login & password setup link |
| `/login/` | Shared login |
| `/account/` | Update own information |
| `/account/password/` | Change password (requires current password) |
| `/account/set-password/` | First-time / forced password setup |
| `/appointments/` | Patient's appointments |
| `/appointments/book/` | Patient books an appointment |
| `/doctor/` | Dentist schedule |
| `/doctor/patients/` | Dentist patient directory |
| `/doctor/patients/new/` | Dentist registers a new patient |
| `/doctor/patients/<id>/` | Patient details, reset password & activation link |
| `/doctor/appointments/new/` | Dentist schedules an appointment |
| `/appointment/<token>/` | Public appointment detail (no login) |
| `/admin/` | Django admin |

## REST API

| Method | URL | Description |
| --- | --- | --- |
| POST | `/api/patient/create` | Create a patient |
| POST | `/api/doctor/create` | Create a dentist (staff/admin only) |
| GET | `/api/appointment/` | List appointments (authenticated) |
| POST | `/api/appointment/create` | Create an appointment (authenticated) |
| GET/PUT/PATCH/DELETE | `/api/appointment/<id>/` | Appointment detail (authenticated) |

Serializer passwords are write-only and are never returned.

## Tests

```bash
python manage.py test
```

## Notes for production

- Set a strong, unique `SECRET_KEY` and `DEBUG=False`.
- Configure `ALLOWED_HOSTS` for your domain.
- Serve over HTTPS and enable the secure-cookie/HSTS settings
  (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`,
  `SECURE_HSTS_SECONDS`).
- Dentist accounts can only be created from the Django admin or by a staff user
  through `/api/doctor/create`.
- The public appointment link is protected by an unguessable UUID only; treat
  it like a private share link.
