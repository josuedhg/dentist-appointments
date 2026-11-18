from django.db import migrations


def backfill_patient_profiles(apps, schema_editor):
    """Give existing patient-group users a profile so they have consistent state."""
    User = apps.get_model("auth", "User")
    PatientProfile = apps.get_model("appointments", "PatientProfile")
    patient_ids = (
        User.objects.filter(groups__name="patient")
        .values_list("pk", flat=True)
        .distinct()
    )
    for user_id in patient_ids:
        PatientProfile.objects.get_or_create(
            user_id=user_id, defaults={"must_change_password": False}
        )


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0005_patientprofile"),
    ]

    operations = [
        migrations.RunPython(
            backfill_patient_profiles, migrations.RunPython.noop
        ),
    ]
