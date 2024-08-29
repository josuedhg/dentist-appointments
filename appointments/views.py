from .models import Appointment
from .serializers import AppointmentSerializer, PatientSerializer, \
    DoctorSerializer
from django.contrib.auth.models import User
from rest_framework.generics import RetrieveUpdateDestroyAPIView, \
    CreateAPIView, ListAPIView
from rest_framework import permissions

# Create your views here.


class DoctorCreateView(CreateAPIView):
    model = User
    serializer_class = DoctorSerializer


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
