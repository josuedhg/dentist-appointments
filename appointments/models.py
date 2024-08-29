from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q
from datetime import datetime

# Create your models here.


def date_validator(value):
    today = datetime.today().date()
    if value < today:
        raise ValueError("Date cannot be earlier than %s" % today)


class Appointment(models.Model):
    patient = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='patient',
                                limit_choices_to=Q(groups__name='patient'))
    doctor = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name='doctor',
                               limit_choices_to=Q(groups__name='doctor'))
    date = models.DateField(validators=[date_validator])
    time = models.TimeField()

    def __str__(self):
        return f"{self.patient.first_name} {self.patient.last_name}"\
            f"appointment at {self.date} at {self.time}"

    def save(self, *args, **kwargs):
        date_validator(self.date)
        super().save(*args, **kwargs)
