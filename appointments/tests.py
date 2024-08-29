from django.test import TestCase
from .models import Appointment
from .serializers import AppointmentSerializer
from django.contrib.auth.models import User
from datetime import datetime, timedelta, time

# Create your tests here.


class AppointmentTest(TestCase):

    def test_appointment(self):
        User.objects.create_user(username='Josue', password='1234')
        User.objects.create_user(username='Dr. Josue', password='1234')
        a = Appointment(patient=User.objects.get(username='Josue'),
                        doctor=User.objects.get(username='Dr. Josue'),
                        date=datetime.today().date(),
                        time=time(10, 0, 0))
        a.save()
        self.assertEqual(Appointment.objects.count(), 1)

    def test_appointment_past_date(self):
        User.objects.create_user(username='Josue', password='1234')
        User.objects.create_user(username='Dr. Josue', password='1234')
        yesterday = datetime.today().date() - timedelta(days=1)
        a = Appointment(patient=User.objects.get(username='Josue'),
                        doctor=User.objects.get(username='Dr. Josue'),
                        date=yesterday,
                        time=time(10, 0, 0))
        self.assertRaises(ValueError, a.save)


class AppointmentSerializerTest(TestCase):
    def test_appointment_serializer(self):
        User.objects.create_user(username='Josue', password='1234')
        User.objects.create_user(username='Dr. Josue', password='1234')
        today = datetime.today().date()
        a = Appointment(patient=User.objects.get(username='Josue'),
                        doctor=User.objects.get(username='Dr. Josue'),
                        date=today,
                        time=time(10, 0, 0))
        a.save()
        serializer = AppointmentSerializer(a)
        self.assertEqual(
            serializer.data['patient'],
            User.objects.get(username='Josue').id)
        self.assertEqual(
            serializer.data['doctor'],
            User.objects.get(username='Dr. Josue').id)
        self.assertEqual(serializer.data['date'], str(today))
        self.assertEqual(serializer.data['time'], str(time(10, 0, 0)))
