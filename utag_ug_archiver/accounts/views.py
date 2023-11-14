from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views import View
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout

from django.shortcuts import render, redirect


class LoginView(View):
    template_name = 'login.html'
    def get(self,request):
        return render(request,self.template_name)
    
    def post(self,request):
        email = request.POST.get('email')
        password = request.POST.get('password')
        print(email,password)
        user = authenticate(request,email=email,password=password)
        if user is not None:
            if user.is_admin or user.is_secretary or user.is_member:
                login(request,user)
                messages.success(request,'Logged in successfully')
                return redirect('dashboard:dashboard')
            else:
                messages.error(request,'Unauthorized user')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        else:
            messages.info(request,'Invalid email or password')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        

class LogoutView(View):
    def get(self,request):
        logout(request)
        messages.success(request,'Logged out successfully')
        return redirect('accounts:login')