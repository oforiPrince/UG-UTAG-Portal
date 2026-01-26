from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect

from dashboard.models import Announcement
from accounts.models import School, College, Department
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
        
        # Get all schools, colleges, departments for dropdowns
        schools = School.objects.all()
        colleges = College.objects.all()
        departments = Department.objects.all()
        
        context = {
            'new_announcements' : new_announcements,
            'announcement_count' : announcement_count,
            'schools': schools,
            'colleges': colleges,
            'departments': departments,
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
        academic_rank = request.POST.get('academic_rank')
        school_id = request.POST.get('school_id')
        college_id = request.POST.get('college_id')
        department_id = request.POST.get('department_id')
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
        
        if user.academic_rank != academic_rank:
            user.academic_rank = academic_rank
        
        # Update school, college, department
        if school_id:
            try:
                user.school = School.objects.get(id=school_id)
            except School.DoesNotExist:
                pass
        else:
            user.school = None
        
        if college_id:
            try:
                user.college = College.objects.get(id=college_id)
            except College.DoesNotExist:
                pass
        else:
            user.college = None
        
        if department_id:
            try:
                user.department = Department.objects.get(id=department_id)
            except Department.DoesNotExist:
                pass
        else:
            user.department = None
        
        # Update executive bio and social media if user is executive
        if user.is_active_executive:
            executive_bio = request.POST.get('executive_bio', '')
            fb_url = request.POST.get('fb_profile_url', '')
            twitter_url = request.POST.get('twitter_profile_url', '')
            linkedin_url = request.POST.get('linkedin_profile_url', '')
            
            if user.executive_bio != executive_bio:
                user.executive_bio = executive_bio
            if user.fb_profile_url != fb_url:
                user.fb_profile_url = fb_url
            if user.twitter_profile_url != twitter_url:
                user.twitter_profile_url = twitter_url
            if user.linkedin_profile_url != linkedin_url:
                user.linkedin_profile_url = linkedin_url

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
        use_as_executive_image = request.POST.get('use_as_executive_image')
        if profile_picture:
            user.profile_pic = profile_picture
            # If the user is an active executive and opted in, set executive image too
            if user.is_active_executive and use_as_executive_image:
                user.executive_image = profile_picture
            user.save()
            messages.info(request, "Profile Picture Updated Successfully")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
