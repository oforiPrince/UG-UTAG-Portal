from datetime import datetime
import random
import string

from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import PermissionRequiredMixin
from accounts.models import User
from dashboard.models import Announcement, Notification
from utag_ug_archiver.utils.constants import executive_committee_members_position_order
from utag_ug_archiver.utils.functions import executive_members_custom_order
from django.contrib.auth.models import Group
from utag_ug_archiver.utils.decorators import MustLogin

#For Executives
class ExecutiveMembersView(PermissionRequiredMixin,View):
    template_name = 'dashboard_pages/executive_members.html'
    permission_required = 'accounts.view_dashboard'
    @method_decorator(MustLogin)
    def get(self, request):
        # Get all executive officers
        executive_officers = User.objects.filter(executive_position__in=executive_committee_members_position_order, is_active_executive=True)
        # Sort the executive officers based on the custom order
        executive_officers = sorted(executive_officers, key=lambda x: executive_committee_members_position_order.index(x.executive_position) if x.executive_position in executive_committee_members_position_order else len(executive_committee_members_position_order))

        # Get all members
        members = User.objects.all()
        print(members)

        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()

        context = {
            'executive_officers': executive_officers,
            'members': members,
            'notifications': notifications,
            'notification_count': notification_count,
        }
        return render(request, self.template_name, context)

class NewExecutiveMemberCreateView(View):
    def post(self, request):
        # Extract fields from POST request
        title = request.POST.get('title')
        first_name = request.POST.get('first_name')
        other_name = request.POST.get('other_name')
        last_name = request.POST.get('last_name')
        gender = request.POST.get('gender')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone')

        # Fields for executive
        position_name = request.POST.get('position')
        fb_username = request.POST.get('fb_username')
        twitter_username = request.POST.get('twitter_username')
        linkedin_username = request.POST.get('linkedin_username')
        date_appointed_str = request.POST.get('date_appointed')
        print(date_appointed_str)
        executive_image = request.FILES.get('image')
        print(executive_image)
        # Handle password
        if request.POST.get('password_choice') == 'auto':
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        else:
            password = request.POST.get('password1')

        # Validation
        if not email or not date_appointed_str:
            messages.info(request, 'Email and date appointed are required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        if User.objects.filter(email=email).exists():
            messages.info(request, 'Member already exists!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Check if date appointed is valid
        # try:
        #     date_appointed = datetime.strptime(date_appointed_str, "%d %b, %Y").date()
        #     print(date_appointed)
        # except ValueError:
        #     messages.info(request, 'Invalid date format! Use "dd Mon, yyyy".')
        #     return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Create User
        member = User.objects.create(
            title=title,
            first_name=first_name,
            other_name=other_name,
            last_name=last_name,
            gender=gender,
            email=email,
            phone_number=phone_number,
            password=make_password(password),
            executive_position=position_name,  # Set executive position
            executive_image = executive_image,
            fb_profile_url=fb_username,        # Set social media URLs
            twitter_profile_url=twitter_username,
            linkedin_profile_url=linkedin_username,
            date_appointed=date_appointed_str,
            is_active_executive=True,          # Mark as active executive
        )
        # Add to executive group
        member.groups.add(Group.objects.get(name='Member'))
        member.groups.add(Group.objects.get(name='Executive'))

        # Send email to admin with password
        # send_credentials_email(member, password)

        messages.success(request, 'Executive Member created successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class ExistingExecutiveMemberCreateView(View):
    def post(self, request):
        member_id = request.POST.get('member_id')
        position = request.POST.get('position')
        fb_username = request.POST.get('fb_username')
        twitter_username = request.POST.get('twitter_username')
        linkedin_username = request.POST.get('linkedin_username')
        date_appointed = request.POST.get('date_appointed')
        executive_image = request.FILES.get('image')
        print(position)
        print(member_id)
        # Retrieve the member
        try:
            member = User.objects.get(id=member_id)
        except User.DoesNotExist:
            messages.info(request, 'Member does not exist!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Check if the member is already an executive
        if member.is_active_executive:
            messages.info(request, 'Member already exists in the executive!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Check if date appointed is valid
        if not date_appointed:
            messages.info(request, 'Date appointed is required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # try:
        #     # Convert date string to datetime object
        #     input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")
        #     formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
        # except ValueError:
        #     messages.info(request, 'Invalid date format! Use "dd Mon, yyyy".')
        #     return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Update member to executive
        member.executive_position = position
        member.fb_profile_url = fb_username
        member.twitter_profile_url = twitter_username
        member.linkedin_profile_url = linkedin_username
        member.date_appointed = date_appointed
        member.executive_image = executive_image
        member.is_active_executive = True
        member.save()
        
        # Add to executive group
        member.groups.add(Group.objects.get(name='Executive'))

        messages.success(request, 'Executive member created successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class UpdateExecutiveMemberView(View):
    def post(self, request):
        executive_id = request.POST.get('executive_id')
        position = request.POST.get('position')
        fb_username = request.POST.get('fb_username')
        twitter_username = request.POST.get('twitter_username')
        linkedin_username = request.POST.get('linkedin_username')
        date_appointed = request.POST.get('date_appointed')
        date_ended = request.POST.get('date_ended')
        active = request.POST.get('active')
        executive_image = request.FILES.get('image')
        
        # Retrieve the executive officer
        try:
            executive = User.objects.get(id=executive_id, is_active_executive=True)
        except User.DoesNotExist:
            messages.info(request, 'Executive Member does not exist!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Check if date appointed is valid
        if not date_appointed:
            messages.info(request, 'Date appointed is required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Update the executive officer's details
        executive.executive_position = position
        executive.fb_profile_url = fb_username
        executive.twitter_profile_url = twitter_username
        executive.linkedin_profile_url = linkedin_username
        executive.date_appointed = date_appointed
        executive.date_ended = date_ended if date_ended else None
        executive.is_active_executive = True if active == 'on' else False
        if executive_image:
            executive.executive_image = executive_image
        executive.save()

        messages.success(request, 'Executive Member updated successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class ExecutiveMemberDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        officer_id = kwargs.get('officer_id')
        try:
            # Retrieve the officer (executive) by ID
            officer = User.objects.get(id=officer_id, is_active_executive=True)
        except User.DoesNotExist:
            messages.info(request, 'Member not found!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        
        officer.is_active_executive = False
        officer.save()
        
        # Remove from executive group
        officer.groups.remove(Group.objects.get(name='Executive'))
        print(officer.groups.all())

        messages.success(request, 'Member removed from executive successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))