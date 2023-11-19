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
from dashboard.models import Executive, Event, News, Document, ExecutivePosition
from utag_ug_archiver.utils.constants import officers_position_order, committee_members_position_order
from utag_ug_archiver.utils.functions import officers_custom_order, members_custom_order, process_bulk_admins, process_bulk_members

from utag_ug_archiver.utils.decorators import MustLogin

class DashboardView(View):
    template_name = 'dashboard_pages/dashboard.html'
    
    @method_decorator(MustLogin)
    def get(self,request):
        total_internal_documents = Document.objects.filter(category='internal').count()
        total_external_documents = Document.objects.filter(category='external').count()
        print(total_external_documents)
        total_executives = Executive.objects.filter(is_active=True).count()
        total_members = User.objects.filter(is_member=True).count()
        total_admins = User.objects.filter(is_admin=True).count()
        total_secretaries = User.objects.filter(is_secretary=True).count()
        published_events = Event.objects.filter(is_published=True).order_by('-date')[:5]
        recent_added_documents = Document.objects.all().order_by('-created_at')[:6]
        context = {
            'total_internal_documents' : total_internal_documents,
            'total_external_documents' : total_external_documents,
            'total_executives' : total_executives,
            'total_members' : total_members,
            'total_admins' :total_admins,
            'total_secretaries': total_secretaries,
            'published_events' : published_events,
            'recent_added_documents' : recent_added_documents
        }
        return render(request, self.template_name, context)
    
#For account management
class AdminListView(View):
    template_name = 'dashboard_pages/admins.html'
    def get(self, request):
        admins = User.objects.filter(is_admin = True).order_by('first_name')
        total_internal_documents = Document.objects.filter(category='internal').count()
        total_external_documents = Document.objects.filter(category='external').count()
        # total_executives = 
        context = {
            'admins' : admins,
            'total_internal_documents' : total_external_documents,
            'total_internal_documents' : total_internal_documents
        }
        return render(request, self.template_name, context)
    
class AdminCreateView(View):
    password = ""
    def post(self, request):
        title = request.POST.get('title')
        first_name = request.POST.get('first_name')
        other_name = request.POST.get('other_name')
        last_name = request.POST.get('last_name')
        gender = request.POST.get('gender')
        email = request.POST.get('email')
        if request.POST.get('password_choice') == 'auto':
            password_length = 10
            self.password = ''.join(random.choices(string.ascii_letters + string.digits, k=password_length))
        else:
            password = request.POST.get('password1')
            self.password = password
        member_exists = User.objects.filter(email=email).exists()
        if member_exists:
            messages.error(request, 'Admin already exists!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        else:
            admin = User.objects.create(
                title = title,
                first_name = first_name,
                other_name = other_name,
                last_name = last_name,
                gender = gender,
                email = email,
                password = make_password(self.password),
                is_admin = True,
            )
            admin.save()
            #TODO = Send email to admin with password
            
            messages.success(request, 'Admin created successfully!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class AdminUpdateView(View):
    def post(self,request):
        admin_id = request.POST.get('admin_id')
        title = request.POST.get('title')
        first_name = request.POST.get('first_name')
        other_name = request.POST.get('other_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        
        admin = User.objects.get(id=admin_id)
        if admin.email != email:
            admin.email = email
        if admin.first_name != first_name:
            admin.first_name = first_name
            
        if admin.other_name != other_name:
            admin.other_name = other_name
            
        if admin.last_name != last_name:
            admin.last_name = last_name
            
        if admin.title != title:
            admin.title = title
            
        admin.save()
        messages.success(request, 'Admin updated successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        
        
class AdminDeleteView(View):
    def get(self, request, *args, **kwargs):
        admin_id = kwargs.get('admin_id')
        admin = User.objects.get(id=admin_id)
        admin.delete()
        messages.success(request, 'Admin deleted successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class MemberCreateView(View):
    password = ""
    def post(self, request):
        title = request.POST.get('title')
        first_name = request.POST.get('first_name')
        other_name = request.POST.get('other_name')
        last_name = request.POST.get('last_name')
        gender = request.POST.get('gender')
        email = request.POST.get('email')
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
            admin = User.objects.create(
                title = title,
                first_name = first_name,
                other_name = other_name,
                last_name = last_name,
                gender = gender,
                email = email,
                password = make_password(self.password),
                is_member = True,
            )
            admin.save()
            #TODO = Send email to admin with password
            
            messages.success(request, 'Member created successfully!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class MemberUpdateView(View):
    def post(self,request):
        admin_id = request.POST.get('admin_id')
        title = request.POST.get('title')
        first_name = request.POST.get('first_name')
        other_name = request.POST.get('other_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        
        admin = User.objects.get(id=admin_id)
        if admin.email != email:
            admin.email = email
        if admin.first_name != first_name:
            admin.first_name = first_name
            
        if admin.other_name != other_name:
            admin.other_name = other_name
            
        if admin.last_name != last_name:
            admin.last_name = last_name
            
        if admin.title != title:
            admin.title = title
            
        admin.save()
        messages.success(request, 'Admin updated successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class MemberDeleteView(View):
    def get(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        member = User.objects.get(id=member_id)
        member.delete()
        messages.success(request, 'Member deleted successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
            

class UploadAdminData(View):
    @method_decorator(MustLogin)
    def post(self, request, *args, **kwargs):
        excel_file = request.FILES.get('excel')
        csv_file = request.FILES.get('csv')

        if excel_file:
            return process_bulk_admins(request, excel_file)
        elif csv_file:
            return process_bulk_admins(request, csv_file)
        else:
            messages.error(request, 'No file uploaded.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class UploadMemberData(View):
    @method_decorator(MustLogin)
    def post(self, request, *args, **kwargs):
        excel_file = request.FILES.get('excel')
        csv_file = request.FILES.get('csv')

        if excel_file:
            return process_bulk_members(request, excel_file)
        elif csv_file:
            return process_bulk_members(request, csv_file)
        else:
            messages.error(request, 'No file uploaded.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

class MemberListView(View):
    template_name = 'dashboard_pages/members.html'
    @method_decorator(MustLogin)
    def get(self, request):
        members = User.objects.filter(is_member = True).order_by('first_name')
        context = {
            'members' : members
        }
        return render(request, self.template_name, context)
    
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
        context = {
            'executive_officers' : executive_officers,
            'members' : members,
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
            input_date = datetime.strptime(date_appointed, "%d %b, %Y")

            # Format the date as YYYY-MM-DD
            formatted_appointed_date = input_date.strftime("%Y-%m-%d")
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
        # Get all executives
        executive_committee_members = Executive.objects.filter(position__name__in=officers_position_order+committee_members_position_order, is_active=True)
        print(executive_committee_members)
        # Sort the executives based on the custom order
        executive_committee_members = sorted(executive_committee_members, key=members_custom_order)
        context = {
            'executive_committee_members' : executive_committee_members
        }
        return render(request, self.template_name, context)
    
class CommitteeMemberDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        c_member_id = kwargs.get('c_member_id')
        c_member = Executive.objects.get(id=c_member_id)
        c_member.delete()
        messages.success(request, 'Officer deleted successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

#For File Management
class InternalDocumentsView(View):
    template_name = 'dashboard_pages/internal_documents.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all internal documents
        internal_documents = Document.objects.filter(category='internal')
        context = {
            'internal_documents' : internal_documents
        }
        return render(request, self.template_name, context)
    
class ExternalDocumentsView(View):
    template_name = 'dashboard_pages/external_documents.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all external documents
        external_documents = Document.objects.filter(category='external')
        context = {
            'external_documents' : external_documents
        }
        return render(request, self.template_name, context)





#For Events and News
class EventsView(View):
    template_name = 'dashboard_pages/events.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all events
        events = Event.objects.all()
        context = {
            'events' : events
        }
        return render(request, self.template_name, context)
    
class EventCreateView(View):
    @method_decorator(MustLogin)
    def get(self, request):
        return render(request, self.template_name)
    
    @method_decorator(MustLogin)
    def post(self, request):
        title = request.POST.get('title')
        content = request.POST.get('content')
        date = request.POST.get('date')
        time = request.POST.get('time')
        venue = request.POST.get('venue')
        is_published = request.POST.get('is_published')
        featured_image = request.FILES.get('featured_image')
        event = Event.objects.create(
            title = title,
            content = content,
            date = date,
            time = time,
            venue = venue,
            is_published = is_published,
            featured_image = featured_image
        )
        event.save()
        messages.info(request, "Event Created Successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class EventUpdateView(View):
    @method_decorator(MustLogin)
    def get(self, request, pk):
        event = Event.objects.get(pk=pk)
        context = {
            'event' : event
        }
        return render(request, self.template_name, context)
    
    @method_decorator(MustLogin)
    def post(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        event = Event.objects.get(pk=event_id)
        title = request.POST.get('title')
        content = request.POST.get('content')
        date = request.POST.get('date')
        time = request.POST.get('time')
        venue = request.POST.get('venue')
        is_published = request.POST.get('is_published')
        featured_image = request.FILES.get('featured_image')
        if featured_image:
            event.featured_image = featured_image
            event.save()
        event.title = title
        event.content = content
        event.date = date
        event.time = time
        event.venue = venue
        event.is_published = is_published
        event.save()
        messages.info(request, "Event Updated Successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class EventDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        event = Event.objects.get(id=event_id)
        event.delete()
        messages.success(request, 'Event deleted successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class NewsView(View):
    template_name = 'dashboard_pages/news.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all news
        news = News.objects.all()
        context = {
            'newss' : news
        }
        return render(request, self.template_name, context)


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
        
class TryPageView(View):
    template_name = 'dashboard_pages/try.html'
    def get(self, request):
        return render(request, self.template_name)