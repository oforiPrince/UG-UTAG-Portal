from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect


from dashboard.models import Announcement
from utag_ug_archiver.utils.decorators import MustLogin

#For user's profile
class ProfileView(View):
    template_name = 'dashboard_pages/profile.html'
    @method_decorator(MustLogin)
    def get(self,request):
        if request.user.is_admin:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif request.user.is_secretary or request.user.is_executive:
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Member').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Member').order_by('-created_at')[:3]
        elif request.user.is_member:
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Executive').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Executive').order_by('-created_at')[:3]
        context = {
            'new_announcements' : new_announcements,
            'announcement_count' : announcement_count
        }
        return render(request, self.template_name, context)
    
    @method_decorator(MustLogin)
    def post(self, request):
        user = request.user
        title = request.POST.get('title')
        # use other_name and surname only
        other_name = request.POST.get('other_name')
        surname = request.POST.get('surname')
        phone = request.POST.get('phone')
        current_password = request.POST.get('current_password')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        # Update user details
        if user.title != title:
            user.title = title
        # store names using other_name and surname
        if user.other_name != other_name:
            user.other_name = other_name
        if getattr(user, 'surname', None) != surname:
            user.surname = surname

        if user.phone_number != phone:
            user.phone_number = phone

        user.save()

        # Check if the user wants to change the password
        if current_password or password or confirm_password:
            if not user.check_password(current_password):
                messages.error(request, "Incorrect current password")
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

            if password != confirm_password:
                messages.error(request, "Passwords do not match")
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

            if password.strip():
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
        
