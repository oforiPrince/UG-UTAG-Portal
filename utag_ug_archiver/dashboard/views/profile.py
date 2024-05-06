from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect


from utag_ug_archiver.utils.decorators import MustLogin

#For user's profile
class ProfileView(View):
    template_name = 'dashboard_pages/profile.html'
    @method_decorator(MustLogin)
    def get(self,request):
        return render(request, self.template_name)
    
    @method_decorator(MustLogin)
    def post(self, request):
        user = request.user
        title = request.POST.get('title')
        first_name = request.POST.get('first_name')
        other_name = request.POST.get('other_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        current_password = request.POST.get('current_password')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if current_password is not None:
            if not user.check_password(current_password):
                messages.error(request, "Incorrect current password")
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
        if user.email != email:
            user.email = email
            user.save()
        
        if user.first_name != first_name:
            user.first_name = first_name
            user.save()

        if user.other_name != other_name:
            user.other_name = other_name
            user.save()
            
        if user.last_name != last_name:
            user.last_name = last_name
            user.save()
            
        if user.title != title:
            user.title = title
            user.save()
            
        if password.strip() != "":
            user.set_password(password)
            user.save()
            
        messages.info(request, "Profile Updated Successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

class ChangeProfilePicView(View):    
    @method_decorator(MustLogin)
    def get(self, request):
        return redirect('dashboard:profile')
    
    @method_decorator(MustLogin)
    def post(self, request):
        user = request.user
        profile_picture = request.FILES.get('profile_picture')
        if profile_picture:
            user.profile_pic = profile_picture
            user.save()
            messages.info(request, "Profile Picture Updated Successfully")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))