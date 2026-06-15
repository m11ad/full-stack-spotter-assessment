from django.urls import path
from . import views

urlpatterns = [
    path('eld/', views.eld_route),
]
