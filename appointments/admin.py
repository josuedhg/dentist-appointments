from urllib.parse import unquote

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group

from .models import Appointment, Dentist, DentistProfile, PatientProfile


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "doctor", "date", "time", "status")
    list_filter = ("status", "date", "doctor")
    search_fields = (
        "patient__username",
        "patient__first_name",
        "patient__last_name",
        "doctor__username",
        "doctor__first_name",
        "doctor__last_name",
    )
    date_hierarchy = "date"
    readonly_fields = ("access_token", "created_at")
    ordering = ("date", "time")


class DentistCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Dentist
        fields = ("username", "first_name", "last_name", "email")


class DentistChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Dentist
        fields = ("username", "first_name", "last_name", "email", "is_active")


@admin.register(Dentist)
class DentistAdmin(UserAdmin):
    """Admin-only dentist management.

    New dentists are created here with a temporary password. The first time
    they log in, the app forces them to choose their own password.
    """

    add_form = DentistCreationForm
    form = DentistChangeForm
    model = Dentist
    list_display = ("username", "first_name", "last_name", "email", "is_active")
    list_filter = ("is_active",)
    search_fields = ("username", "first_name", "last_name", "email")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        ("Account", {"fields": ("is_active",)}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "first_name",
                    "last_name",
                    "email",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(groups__name="doctor")
            .distinct()
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        doctor_group, _ = Group.objects.get_or_create(name="doctor")
        obj.groups.add(doctor_group)
        if not change:
            DentistProfile.objects.update_or_create(
                user=obj, defaults={"must_change_password": True}
            )

    def user_change_password(self, request, id, form_url=""):
        """When an admin resets a dentist's password, force a change on the
        next login as well.
        """
        response = super().user_change_password(request, id, form_url)
        if request.method == "POST" and response.status_code == 302:
            user_id = unquote(id)
            DentistProfile.objects.update_or_create(
                user_id=user_id, defaults={"must_change_password": True}
            )
            messages.info(
                request,
                "The dentist will be asked to choose a new password on their "
                "next login.",
            )
        return response


@admin.register(DentistProfile)
class DentistProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "must_change_password", "created_at")
    list_filter = ("must_change_password",)
    search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "must_change_password", "created_at")
    list_filter = ("must_change_password",)
    search_fields = ("user__username", "user__first_name", "user__last_name")
    readonly_fields = ("login_token", "created_at")
