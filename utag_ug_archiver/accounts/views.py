from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views import View
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout

from django.shortcuts import render, redirect


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
            print(f"User '{user.first_name}' belongs to groups: {user_groups}")
            
            # Check if user belongs to the required groups
            required_groups = {'Admin', 'Secretary', 'Executive', 'Member', 'Committee Member'}
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
        

class LogoutView(View):
    def get(self,request):
        logout(request)
        messages.success(request,'Logged out successfully')
        return redirect('accounts:login')