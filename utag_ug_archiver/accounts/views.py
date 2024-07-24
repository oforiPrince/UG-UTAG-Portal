from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views import View
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator as token_generator
from django.template.loader import render_to_string
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.contrib.auth.forms import SetPasswordForm
from django.core.mail import EmailMessage

from accounts.models import User
from utag_ug_archiver import settings
from utag_ug_archiver.utils.functions import send_reset_password_email


class LoginView(View):
    template_name = 'login.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Authenticate the user
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            # Fetch and print the user's groups
            user_groups = user.groups.values_list('name', flat=True)
            
            # Check if user belongs to the required groups
            required_groups = {'Admin','Executive', 'Member'}
            user_groups_set = set(user_groups)
            
            if user_groups_set & required_groups:  # Check if there's any intersection
                # Check if the user has the permission to access the dashboard
                if user.has_perm('accounts.view_dashboard'):
                    login(request, user)
                    messages.success(request, 'Logged in successfully')
                    return redirect('dashboard:dashboard')
                else:
                    messages.error(request, 'You do not have permission to access the dashboard')
                    return redirect(request.META.get('HTTP_REFERER', '/'))
            else:
                messages.error(request, 'Unauthorized user')
                return redirect(request.META.get('HTTP_REFERER', '/'))
        else:
            messages.info(request, 'Invalid email or password')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
class ForgotPasswordView(View):
    def get(self, request):
        return render(request, 'forgot_password.html')
    
    def post(self, request):
        email = request.POST['email']
        try:
            user = User.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)
            reset_url = request.build_absolute_uri(reverse('accounts:password_reset_confirm', args=[uid, token]))
            # subject = 'Password Reset Request'
            # message = render_to_string('emails/password_reset_email.html', {
            #     'user': user,
            #     'reset_url': reset_url
            # })
            # send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email])
            send_reset_password_email(user,reset_url)
            messages.success(request, 'An email has been sent to reset your password.')
        except User.DoesNotExist:
            messages.error(request, 'No user with this email exists.')
        return redirect('accounts:forgot_password')
    
class PasswordResetConfirmView(View):
    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            if token_generator.check_token(user, token):
                return render(request, 'password_reset_confirm.html', {'form': SetPasswordForm(user), 'uidb64': uidb64, 'token': token})
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        return render(request, 'password_reset_confirm_invalid.html')
    
    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            if token_generator.check_token(user, token):
                form = SetPasswordForm(user, request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, 'Your password has been reset successfully.')
                    return redirect('accounts:login')
                else:
                    return render(request, 'password_reset_confirm.html', {'form': form, 'uidb64': uidb64, 'token': token})
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        return render(request, 'password_reset_confirm_invalid.html')
        

class LogoutView(View):
    def get(self,request):
        logout(request)
        messages.success(request,'Logged out successfully')
        return redirect('accounts:login')