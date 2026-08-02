from django.urls import path
from .views import ExecutivesListView, ExecutiveDetailView

urlpatterns = [
    path('executives/', ExecutivesListView.as_view(), name='executives_list'),
    path('executives/<int:pk>/', ExecutiveDetailView.as_view(), name='executive_detail'),
]
