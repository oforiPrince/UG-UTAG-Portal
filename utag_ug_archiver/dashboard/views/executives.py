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
from dashboard.models import Announcement
from utag_ug_archiver.utils.constants import officers_position_order, committee_members_position_order
from utag_ug_archiver.utils.functions import officers_custom_order, members_custom_order
from django.contrib.auth.models import Group
from utag_ug_archiver.utils.decorators import MustLogin

#For Executives
class ExecutiveOfficersView(PermissionRequiredMixin,View):
    template_name = 'dashboard_pages/executive_officers.html'
    permission_required = 'accounts.view_dashboard'
    @method_decorator(MustLogin)
    def get(self, request):
        # Get all executive officers
        executive_officers = User.objects.filter(executive_position__in=officers_position_order, is_active_executive=True)
        # Sort the executive officers based on the custom order
        executive_officers = sorted(executive_officers, key=lambda x: officers_position_order.index(x.executive_position) if x.executive_position in officers_position_order else len(officers_position_order))

        # Get all members
        members = User.objects.filter(groups__name='Member')

        # Determine announcements based on user role
        if request.user.groups.filter(name='Admin').exists():
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif request.user.groups.filter(name='Secretary').exists() or request.user.groups.filter(name='Executive').exists():
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Member').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Member').count()
        elif request.user.groups.filter(name='Member').exists():
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Executive').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_groups__name='Executive').count()

        context = {
            'executive_officers': executive_officers,
            'members': members,
            'new_announcements': new_announcements,
            'announcement_count': announcement_count,
        }
        return render(request, self.template_name, context)

class NewOfficerCreateView(View):
    def post(self, request):
        # Extract fields from POST request
        title = request.POST.get('title')
        first_name = request.POST.get('first_name')
        other_name = request.POST.get('other_name')
        last_name = request.POST.get('last_name')
        gender = request.POST.get('gender')
        email = request.POST.get('email')

        # Fields for executive
        position_name = request.POST.get('position')
        fb_username = request.POST.get('fb_username')
        twitter_username = request.POST.get('twitter_username')
        linkedin_username = request.POST.get('linkedin_username')
        date_appointed_str = request.POST.get('date_appointed')

        # Handle password
        if request.POST.get('password_choice') == 'auto':
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        else:
            password = request.POST.get('password1')

        # Validation
        if not email or not date_appointed_str:
            messages.error(request, 'Email and date appointed are required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Member already exists!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Check if date appointed is valid
        try:
            date_appointed = datetime.strptime(date_appointed_str, "%d %b, %Y").date()
        except ValueError:
            messages.error(request, 'Invalid date format! Use "dd Mon, yyyy".')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Create User
        member = User.objects.create(
            title=title,
            first_name=first_name,
            other_name=other_name,
            last_name=last_name,
            gender=gender,
            email=email,
            password=make_password(password),
            executive_position=position_name,  # Set executive position
            fb_profile_url=fb_username,        # Set social media URLs
            twitter_profile_url=twitter_username,
            linkedin_profile_url=linkedin_username,
            date_appointed=date_appointed,
            is_active_executive=True,          # Mark as active executive
        )
        # Add to executive group
        member.groups.add(Group.objects.get(name='Executive'))

        # Send email to admin with password
        # send_credentials_email(member, password)

        messages.success(request, 'Executive Officer created successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class ExistingExecutiveOfficerCreateView(View):
    def post(self, request):
        member_id = request.POST.get('member_id')
        position = request.POST.get('position')
        fb_username = request.POST.get('fb_username')
        twitter_username = request.POST.get('twitter_username')
        linkedin_username = request.POST.get('linkedin_username')
        date_appointed = request.POST.get('date_appointed')
        if position == '' or position is None:
            position = 'Committee Member'
        print(position)
        print(member_id)
        # Retrieve the member
        try:
            member = User.objects.get(id=member_id)
        except User.DoesNotExist:
            messages.error(request, 'Member does not exist!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Check if the member is already an executive
        if member.is_active_executive:
            messages.error(request, 'Member already exists in the executive!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Check if date appointed is valid
        if not date_appointed:
            messages.error(request, 'Date appointed is required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        try:
            # Convert date string to datetime object
            input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")
            formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
        except ValueError:
            messages.error(request, 'Invalid date format! Use "dd Mon, yyyy".')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Update member to executive
        member.executive_position = position
        member.fb_profile_url = fb_username
        member.twitter_profile_url = twitter_username
        member.linkedin_profile_url = linkedin_username
        member.date_appointed = formatted_appointed_date
        member.is_active_executive = True
        member.save()
        
        # Add to executive group
        member.groups.add(Group.objects.get(name='Executive'))
        print(member.groups.all())

        messages.success(request, 'Executive member created successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class UpdateExecutiveOfficerView(View):
    def post(self, request):
        executive_id = request.POST.get('executive_id')
        position = request.POST.get('position')
        fb_username = request.POST.get('fb_username')
        twitter_username = request.POST.get('twitter_username')
        linkedin_username = request.POST.get('linkedin_username')
        date_appointed = request.POST.get('date_appointed')
        date_ended = request.POST.get('date_ended')
        active = request.POST.get('active')
        
        # Retrieve the executive officer
        try:
            executive = User.objects.get(id=executive_id, is_active_executive=True)
        except User.DoesNotExist:
            messages.error(request, 'Executive Officer does not exist!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Check if date appointed is valid
        if not date_appointed:
            messages.error(request, 'Date appointed is required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        try:
            # Convert date string to datetime object
            input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")
            formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
        except ValueError:
            messages.error(request, 'Invalid date format! Use "dd Mon, yyyy".')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        try:
            input_date_ended = datetime.strptime(date_ended, "%d %b, %Y") if date_ended else None
            formatted_date_ended = input_date_ended.strftime("%Y-%m-%d") if input_date_ended else None
        except ValueError:
            messages.error(request, 'Invalid end date format! Use "dd Mon, yyyy".')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Update the executive officer's details
        executive.executive_position = position
        executive.fb_profile_url = fb_username
        executive.twitter_profile_url = twitter_username
        executive.linkedin_profile_url = linkedin_username
        executive.date_appointed = formatted_appointed_date
        executive.date_ended = formatted_date_ended
        executive.is_active_executive = True if active == 'on' else False
        executive.save()

        messages.success(request, 'Executive Officer updated successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class OfficerDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        officer_id = kwargs.get('officer_id')
        try:
            # Retrieve the officer (executive) by ID
            officer = User.objects.get(id=officer_id, is_active_executive=True)
        except User.DoesNotExist:
            messages.error(request, 'Officer not found!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        
        officer.is_active_executive = False
        officer.save()
        
        # Remove from executive group
        officer.groups.remove(Group.objects.get(name='Executive'))
        print(officer.groups.all())

        messages.success(request, 'Officer removed from executive successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

class ExecutiveCommitteeMembersView(View):
    template_name = 'dashboard_pages/executive_committee_members.html'
    
    @method_decorator(MustLogin)
    def get(self, request):
        members = User.objects.filter(groups__name='Member')
        # Get all active executive committee members
        executive_committee_members = User.objects.filter(
            executive_position__in=officers_position_order + committee_members_position_order,
            is_active_executive=True
        )
        
        announcement_count = 0
        new_announcements = []

        if request.user.is_admin:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif request.user.groups.filter(name='Secretary').exists() or request.user.is_active_executive:
            announcement_count = Announcement.objects.filter(status='PUBLISHED', target_groups__name='Executive').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED', target_groups__name='Executive').order_by('-created_at')[:3]
        elif request.user.is_member:
            announcement_count = Announcement.objects.filter(status='PUBLISHED', target_groups__name='Member').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED', target_groups__name='Member').order_by('-created_at')[:3]

        # Custom order sorting
        def members_custom_order(member):
            position_order = officers_position_order + committee_members_position_order
            try:
                return position_order.index(member.executive_position)
            except ValueError:
                return len(position_order)
        
        # Sort the executive committee members based on the custom order
        executive_committee_members = sorted(executive_committee_members, key=members_custom_order)
        
        context = {
            'executive_officers': executive_committee_members,
            'members': members,
            'new_announcements': new_announcements,
            'announcement_count': announcement_count,
        }
        
        return render(request, self.template_name, context)
    
# class NewCommitteeMemberCreateView(View):
#     password = ""
    
#     def post(self, request):
#         title = request.POST.get('title')
#         first_name = request.POST.get('first_name')
#         other_name = request.POST.get('other_name')
#         last_name = request.POST.get('last_name')
#         gender = request.POST.get('gender')
#         email = request.POST.get('email')
        
#         # Fields for executive
#         position = request.POST.get('position')
#         fb_username = request.POST.get('fb_username')
#         twitter_username = request.POST.get('twitter_username')
#         linkedin_username = request.POST.get('linkedin_username')
#         date_appointed = request.POST.get('date_appointed')
        
#         if request.POST.get('password_choice') == 'auto':
#             password_length = 10
#             self.password = ''.join(random.choices(string.ascii_letters + string.digits, k=password_length))
#         else:
#             password = request.POST.get('password1')
#             self.password = password
        
#         member_exists = User.objects.filter(email=email).exists()
        
#         if member_exists:
#             messages.error(request, 'Member already exists!')
#             return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
#         else:
#             # Check if date appointed is valid
#             if date_appointed == "":
#                 messages.error(request, 'Date appointed is required!')
#                 return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
#             # Check if appointed member is already an executive
#             executive_exists = User.objects.filter(email=email, executive_position__isnull=False).exists()
#             if executive_exists:
#                 messages.error(request, 'Member already exists in the executive!')
#                 return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            
#             # Create member
#             member = User.objects.create(
#                 title=title,
#                 first_name=first_name,
#                 other_name=other_name,
#                 last_name=last_name,
#                 gender=gender,
#                 email=email,
#                 password=make_password(self.password),
#                 is_member=True,
#             )
            
#             # Add member to executive
#             # Convert date string to datetime object
#             input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")
            
#             # Format the date as YYYY-MM-DD
#             formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
            
#             # Update member with executive details
#             member.executive_position = position
#             member.fb_profile_url = fb_username
#             member.twitter_profile_url = twitter_username
#             member.linkedin_profile_url = linkedin_username
#             member.date_appointed = formatted_appointed_date
#             member.is_active_executive = True
#             member.save()
            
#             # TODO: Send email to admin with password
            
#             messages.success(request, 'Committee Member created successfully!')
#             return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
# class ExecutiveCommitteeMemberCreateView(View):
#     def post(self, request):
#         member_id = request.POST.get('member_id')
#         position = request.POST.get('position')
#         fb_username = request.POST.get('fb_username')
#         twitter_username = request.POST.get('twitter_username')
#         linkedin_username = request.POST.get('linkedin_username')
#         date_appointed = request.POST.get('date_appointed')
#         member = User.objects.get(id=member_id)
#         executive_exists = Executive.objects.filter(member__id=member_id).exists()
#         if executive_exists:
#             messages.error(request, 'Member already exists in the executive!')
#             return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
#         #Check if date appointed is valid
#         if date_appointed == "":
#             messages.error(request, 'Date appointed is required!')
#             return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
#         #Add member to executive
#         # Convert date string to datetime object
#         input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")
        
#         # Format the date as YYYY-MM-DD
#         formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
#         position = ExecutivePosition.objects.get(name=position)
#         executive = Executive.objects.create(
#             member = member,
#             position = position,
#             fb_username = fb_username,
#             twitter_username = twitter_username,
#             linkedin_username = linkedin_username,
#             is_executive_officer = False,
#             date_appointed = formatted_appointed_date,
#         )
#         executive.save()
        
#         messages.success(request, 'Executive Officer created successfully!')
#         return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
# class CommitteeMemberUpdateView(View):
#     def post(self, request):
#         executive_id = request.POST.get('executive_id')
#         position = request.POST.get('position')
#         fb_username = request.POST.get('fb_username')
#         twitter_username = request.POST.get('twitter_username')
#         linkedin_username = request.POST.get('linkedin_username')
#         date_appointed = request.POST.get('date_appointed')
#         date_ended = request.POST.get('date_ended')
#         executive = Executive.objects.get(id=executive_id)
#         active = request.POST.get('active')
#         #Check if date appointed is valid
#         if date_appointed == "":
#             messages.error(request, 'Date appointed is required!')
#             return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        
#         # Update the executive
#         # Convert date string to datetime object
#         input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")
#         input_date_ended = datetime.strptime(date_ended, "%d %b, %Y") if date_ended != "" else None
        
        
#         # Format the date as YYYY-MM-DD
#         formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
#         formatted_date_ended = input_date_ended.strftime("%Y-%m-%d") if date_ended != "" else None
#         position = ExecutivePosition.objects.get(name=position)
#         executive.position = position
#         executive.fb_username = fb_username
#         executive.twitter_username = twitter_username
#         executive.linkedin_username = linkedin_username
#         executive.date_appointed = formatted_appointed_date
#         executive.date_ended = formatted_date_ended if date_ended != "" else None
#         if active == 'on':
#             executive.is_active = True
#         else:
#             executive.is_active = False
#         executive.save()
        
#         messages.success(request, 'Executive Officer updated successfully!')
#         return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
# class CommitteeMemberDeleteView(View):
#     @method_decorator(MustLogin)
#     def get(self, request, *args, **kwargs):
#         c_member_id = kwargs.get('c_member_id')
#         c_member = Executive.objects.get(id=c_member_id)
#         c_member.delete()
#         messages.success(request, 'Officer deleted successfully!')
#         return HttpResponseRedirect(request.META.get('HTTP_REFERER'))