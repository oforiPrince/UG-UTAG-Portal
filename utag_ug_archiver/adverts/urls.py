from django.urls import path
from . import views

app_name = 'adverts'

urlpatterns = [
    path('click/<int:pk>/', views.ad_click_redirect, name='click'),
    path('impression/<int:pk>/', views.ad_impression_ping, name='impression'),
]
