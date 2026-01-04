from django.urls import path
from . import views
app_name = 'accounts'
urlpatterns = [
    path('login/',views.LoginView.as_view(), name='login'),
    path('logout/',views.LogoutView.as_view(), name='logout'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),
    path('email-sent/', views.EmailSentView.as_view(), name='email_sent'),
    path('reset/<uidb64>/<token>/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('change-password-required/', views.ChangePasswordRequiredView.as_view(), name='change_password_required'),
]