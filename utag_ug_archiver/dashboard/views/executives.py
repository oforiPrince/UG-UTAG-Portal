from datetime import datetime
import random
import string

from django.contrib.auth.hashers import make_password
from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect



from accounts.models import User
from dashboard.models import Announcement, Executive, ExecutivePosition
from utag_ug_archiver.utils.constants import officers_position_order, committee_members_position_order
from utag_ug_archiver.utils.functions import officers_custom_order, members_custom_order

from utag_ug_archiver.utils.decorators import MustLogin

#For Executives
class ExecutiveOfficersView(View):
    template_name = 'dashboard_pages/executive_officers.html'
    @method_decorator(MustLogin)
    def get(self, request):
        # Get all executive_officers
        executive_officers = Executive.objects.filter(position__name__in=officers_position_order, is_executive_officer=True)
        # Sort the executive_officers based on the custom order
        executive_officers = sorted(executive_officers, key=officers_custom_order)
        
        #Get all members
        members = User.objects.filter(is_member=True)
        announcement_count = 0
        if request.user.is_admin:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif request.user.is_secretary or request.user.is_executive:
            announcement_count = Announcement.objects.filter(status='PUBLISHED', target_group='EXECUTIVES').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED', target_group='EXECUTIVES').order_by('-created_at')[:3]
        elif request.user.is_member:
            announcement_count = Announcement.objects.filter(status='PUBLISHED', target_group='MEMBERS').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED', target_group='MEMBERS').order_by('-created_at')[:3]
        context = {
            'executive_officers' : executive_officers,
            'members' : members,
            'new_announcements' : new_announcements,
            'announcement_count' : announcement_count,
        }
        return render(request, self.template_name, context)

class NewOfficerCreateView(View):
    password = ""
    def post(self, request):
        title = request.POST.get('title')
        first_name = request.POST.get('first_name')
        other_name = request.POST.get('other_name')
        last_name = request.POST.get('last_name')
        gender = request.POST.get('gender')
        email = request.POST.get('email')
        
        #fields for executive
        position = request.POST.get('position')
        fb_username = request.POST.get('fb_username')
        twitter_username = request.POST.get('twitter_username')
        linkedin_username = request.POST.get('linkedin_username')
        date_appointed = request.POST.get('date_appointed')
        if request.POST.get('password_choice') == 'auto':
            password_length = 10
            self.password = ''.join(random.choices(string.ascii_letters + string.digits, k=password_length))
        else:
            password = request.POST.get('password1')
            self.password = password
        member_exists = User.objects.filter(email=email).exists()
        if member_exists:
            messages.error(request, 'Member already exists!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        else:
            #Check if date appointed is valid
            if date_appointed == "":
                messages.error(request, 'Date appointed is required!')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            #Check if appointed member is already an executive
            executive_exists = Executive.objects.filter(member__email=email).exists()
            if executive_exists:
                messages.error(request, 'Member already exists in the executive!')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            #Create member
            member = User.objects.create(
                title = title,
                first_name = first_name,
                other_name = other_name,
                last_name = last_name,
                gender = gender,
                email = email,
                password = make_password(self.password),
                is_member = True,
            )
            member.save()
            #TODO = Send email to admin with password
            
            #Add member to executive
            # Convert date string to datetime object
            input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")

            # Format the date as YYYY-MM-DD
            formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
            position = ExecutivePosition.objects.get(name=position)
            executive = Executive.objects.create(
                member = member,
                position = position,
                fb_username = fb_username,
                twitter_username = twitter_username,
                linkedin_username = linkedin_username,
                is_executive_officer = True,
                date_appointed = formatted_appointed_date,
            )
            executive.save()
            
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
        member = User.objects.get(id=member_id)
        executive_exists = Executive.objects.filter(member__id=member_id).exists()
        if executive_exists:
            messages.error(request, 'Member already exists in the executive!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        #Check if date appointed is valid
        if date_appointed == "":
            messages.error(request, 'Date appointed is required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        #Add member to executive
        # Convert date string to datetime object
        input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")
        
        # Format the date as YYYY-MM-DD
        formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
        position = ExecutivePosition.objects.get(name=position)
        executive = Executive.objects.create(
            member = member,
            position = position,
            fb_username = fb_username,
            twitter_username = twitter_username,
            linkedin_username = linkedin_username,
            is_executive_officer = True,
            date_appointed = formatted_appointed_date,
        )
        executive.save()
        
        messages.success(request, 'Executive Officer created successfully!')
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
        executive = Executive.objects.get(id=executive_id)
        active = request.POST.get('active')
        #Check if date appointed is valid
        if date_appointed == "":
            messages.error(request, 'Date appointed is required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        
        # Update the executive
        # Convert date string to datetime object
        input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")
        input_date_ended = datetime.strptime(date_ended, "%d %b, %Y") if date_ended != "" else None
        
        
        # Format the date as YYYY-MM-DD
        formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
        formatted_date_ended = input_date_ended.strftime("%Y-%m-%d") if date_ended != "" else None
        position = ExecutivePosition.objects.get(name=position)
        executive.position = position
        executive.fb_username = fb_username
        executive.twitter_username = twitter_username
        executive.linkedin_username = linkedin_username
        executive.date_appointed = formatted_appointed_date
        executive.date_ended = formatted_date_ended if date_ended != "" else None
        if active == 'on':
            executive.is_active = True
        else:
            executive.is_active = False
        executive.save()
        
        messages.success(request, 'Executive Officer updated successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class OfficerDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        officer_id = kwargs.get('officer_id')
        print(officer_id)
        officer = Executive.objects.get(id=officer_id)
        officer.delete()
        messages.success(request, 'Officer deleted successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

class ExecutiveCommitteeMembersView(View):
    template_name = 'dashboard_pages/executive_committee_members.html'
    @method_decorator(MustLogin)
    def get(self, request):
        members = User.objects.filter(is_member=True)
        # Get all executives
        executive_committee_members = Executive.objects.filter(position__name__in=officers_position_order+committee_members_position_order, is_active=True)
        announcement_count = 0
        if request.user.is_admin:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif request.user.is_secretary or request.user.is_executive:
            announcement_count = Announcement.objects.filter(status='PUBLISHED', target_group='EXECUTIVES').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED', target_group='EXECUTIVES').order_by('-created_at')[:3]
        elif request.user.is_member:
            announcement_count = Announcement.objects.filter(status='PUBLISHED', target_group='MEMBERS').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED', target_group='MEMBERS').order_by('-created_at')[:3]
        # Sort the executives based on the custom order
        executive_committee_members = sorted(executive_committee_members, key=members_custom_order)
        context = {
            'executive_committee_members' : executive_committee_members,
            'members' : members,
            'new_announcements' : new_announcements,
            'announcement_count' : announcement_count,
        }
        return render(request, self.template_name, context)
    
class NewCommitteeMemberCreateView(View):
    password = ""
    def post(self, request):
        title = request.POST.get('title')
        first_name = request.POST.get('first_name')
        other_name = request.POST.get('other_name')
        last_name = request.POST.get('last_name')
        gender = request.POST.get('gender')
        email = request.POST.get('email')
        
        #fields for executive
        position = request.POST.get('position')
        fb_username = request.POST.get('fb_username')
        twitter_username = request.POST.get('twitter_username')
        linkedin_username = request.POST.get('linkedin_username')
        date_appointed = request.POST.get('date_appointed')
        if request.POST.get('password_choice') == 'auto':
            password_length = 10
            self.password = ''.join(random.choices(string.ascii_letters + string.digits, k=password_length))
        else:
            password = request.POST.get('password1')
            self.password = password
        member_exists = User.objects.filter(email=email).exists()
        if member_exists:
            messages.error(request, 'Member already exists!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        else:
            #Check if date appointed is valid
            if date_appointed == "":
                messages.error(request, 'Date appointed is required!')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            #Check if appointed member is already an executive
            executive_exists = Executive.objects.filter(member__email=email).exists()
            if executive_exists:
                messages.error(request, 'Member already exists in the executive!')
                return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
            #Create member
            member = User.objects.create(
                title = title,
                first_name = first_name,
                other_name = other_name,
                last_name = last_name,
                gender = gender,
                email = email,
                password = make_password(self.password),
                is_member = True,
            )
            member.save()
            #TODO = Send email to admin with password
            
            #Add member to executive
            # Convert date string to datetime object
            input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")

            # Format the date as YYYY-MM-DD
            formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
            position = ExecutivePosition.objects.get(name=position)
            executive_member = Executive.objects.create(
                member = member,
                position = position,
                fb_username = fb_username,
                twitter_username = twitter_username,
                linkedin_username = linkedin_username,
                is_executive_officer = False,
                date_appointed = formatted_appointed_date,
            )
            executive_member.save()
            
            messages.success(request, 'Executive Officer created successfully!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class ExecutiveCommitteeMemberCreateView(View):
    def post(self, request):
        member_id = request.POST.get('member_id')
        position = request.POST.get('position')
        fb_username = request.POST.get('fb_username')
        twitter_username = request.POST.get('twitter_username')
        linkedin_username = request.POST.get('linkedin_username')
        date_appointed = request.POST.get('date_appointed')
        member = User.objects.get(id=member_id)
        executive_exists = Executive.objects.filter(member__id=member_id).exists()
        if executive_exists:
            messages.error(request, 'Member already exists in the executive!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        #Check if date appointed is valid
        if date_appointed == "":
            messages.error(request, 'Date appointed is required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        #Add member to executive
        # Convert date string to datetime object
        input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")
        
        # Format the date as YYYY-MM-DD
        formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
        position = ExecutivePosition.objects.get(name=position)
        executive = Executive.objects.create(
            member = member,
            position = position,
            fb_username = fb_username,
            twitter_username = twitter_username,
            linkedin_username = linkedin_username,
            is_executive_officer = False,
            date_appointed = formatted_appointed_date,
        )
        executive.save()
        
        messages.success(request, 'Executive Officer created successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class CommitteeMemberUpdateView(View):
    def post(self, request):
        executive_id = request.POST.get('executive_id')
        position = request.POST.get('position')
        fb_username = request.POST.get('fb_username')
        twitter_username = request.POST.get('twitter_username')
        linkedin_username = request.POST.get('linkedin_username')
        date_appointed = request.POST.get('date_appointed')
        date_ended = request.POST.get('date_ended')
        executive = Executive.objects.get(id=executive_id)
        active = request.POST.get('active')
        #Check if date appointed is valid
        if date_appointed == "":
            messages.error(request, 'Date appointed is required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        
        # Update the executive
        # Convert date string to datetime object
        input_appointed_date = datetime.strptime(date_appointed, "%d %b, %Y")
        input_date_ended = datetime.strptime(date_ended, "%d %b, %Y") if date_ended != "" else None
        
        
        # Format the date as YYYY-MM-DD
        formatted_appointed_date = input_appointed_date.strftime("%Y-%m-%d")
        formatted_date_ended = input_date_ended.strftime("%Y-%m-%d") if date_ended != "" else None
        position = ExecutivePosition.objects.get(name=position)
        executive.position = position
        executive.fb_username = fb_username
        executive.twitter_username = twitter_username
        executive.linkedin_username = linkedin_username
        executive.date_appointed = formatted_appointed_date
        executive.date_ended = formatted_date_ended if date_ended != "" else None
        if active == 'on':
            executive.is_active = True
        else:
            executive.is_active = False
        executive.save()
        
        messages.success(request, 'Executive Officer updated successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class CommitteeMemberDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        c_member_id = kwargs.get('c_member_id')
        c_member = Executive.objects.get(id=c_member_id)
        c_member.delete()
        messages.success(request, 'Officer deleted successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))