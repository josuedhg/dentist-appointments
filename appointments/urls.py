"""
URL configuration for dentist project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from appointments.views import AppointmentRetrieveUpdateDestroyView, \
    AppointmentListView, AppointmentCreateView, PatientCreateView, \
    DoctorCreateView

urlpatterns = [
    # Patient
    path('api/patient/create', PatientCreateView.as_view(),
         name='patient-create'),
    # Doctor
    path('api/doctor/create', DoctorCreateView.as_view(),
         name='doctor-create'),
    # appointments
    path('api/appointment/', AppointmentListView.as_view(),
         name='appointment-list'),
    path('api/appointment/<int:pk>/',
         AppointmentRetrieveUpdateDestroyView.as_view()),
    path('api/appointment/create', AppointmentCreateView.as_view(),
         name='appointment-create'),
]
