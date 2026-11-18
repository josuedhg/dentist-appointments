from django.db import migrations


def backfill_dentist_profiles(apps, schema_editor):
    """Give existing dentist-group users a profile.

    They already chose their own password before this feature existed, so they
    are not forced to change it. The admin can still toggle the flag later.
    """
    User = apps.get_model("auth", "User")
    DentistProfile = apps.get_model("appointments", "DentistProfile")
    dentist_ids = (
        User.objects.filter(groups__name="doctor")
        .values_list("pk", flat=True)
        .distinct()
    )
    for user_id in dentist_ids:
        DentistProfile.objects.get_or_create(
            user_id=user_id, defaults={"must_change_password": False}
        )


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0003_dentist_dentistprofile"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(
            backfill_dentist_profiles, migrations.RunPython.noop
        ),
    ]
