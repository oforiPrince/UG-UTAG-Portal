import logging
import random
import string
import csv
import os
import uuid
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.hashers import make_password
from django.shortcuts import render
from django.db import transaction
from django.views import View
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.contrib.auth.models import Group
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from accounts.models import User, School, College, Department
from dashboard.models import  Document, Notification
from utag_ug_archiver.utils.functions import process_bulk_admins, process_bulk_members, ensure_staff_id
from dashboard.tasks_bulk_import import import_members_from_upload
from utag_ug_archiver.utils.decorators import MustLogin
# Configure the logger
logger = logging.getLogger(__name__)

#For account management
class AdminListView(PermissionRequiredMixin, View):
    template_name = 'dashboard_pages/admins.html'
    permission_required = 'accounts.view_admin'
    @method_decorator(MustLogin)
    def get(self, request):
        # Fetch users
        users = User.objects.filter(groups__name='Admin').order_by('surname')
        
        # Fetch document counts
        total_documents = Document.objects.filter(category='internal').count()
        total_external_documents = Document.objects.filter(category='external').count()
        
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        # Prepare context
        context = {
            'users': users,
            'total_documents': total_documents,
            'total_external_documents': total_external_documents,
            'notifications': notifications,
            'notification_count': notification_count,
            'has_add_permission': request.user.has_perm('accounts.add_admin'),
            'has_change_permission': request.user.has_perm('accounts.change_admin'),
            'has_delete_permission': request.user.has_perm('accounts.delete_admin'),
            'schools': School.objects.all(),
            'colleges': College.objects.all(),
            'departments': Department.objects.all(),
        }
        
        # Render the template
        return render(request, self.template_name, context)
    
class AdminCreateView(PermissionRequiredMixin, View):
    permission_required = 'accounts.add_admin'
    
    @method_decorator(MustLogin)
    def post(self, request):
        title = request.POST.get('title')
        # primary fields: other_name and surname; accept legacy first_name/last_name
        other_name = request.POST.get('other_name') or request.POST.get('first_name')
        surname = request.POST.get('surname') or request.POST.get('last_name')
        gender = request.POST.get('gender')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone')
        school_id = request.POST.get('school')
        college_id = request.POST.get('college')
        department_id = request.POST.get('department')
        staff_id = request.POST.get('staff_id', '').strip()

        # Validate staff_id
        if not staff_id:
            messages.error(request, 'Staff ID is required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Check if staff_id already exists
        if User.objects.filter(staff_id=staff_id).exists():
            messages.error(request, 'Staff ID already exists. Please use a different Staff ID.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        member_exists = User.objects.filter(email=email).exists()
        if member_exists:
            messages.error(request, 'Admin already exists!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        try:
            with transaction.atomic():
                # Create user
                admin = User.objects.create(
                    title=title,
                    other_name=other_name,
                    surname=surname,
                    gender=gender,
                    email=email,
                    phone_number=phone_number,
                    school_id=school_id if school_id else None,
                    college_id=college_id if college_id else None,
                    department_id=department_id if department_id else None,
                    staff_id=staff_id,
                    created_by=request.user,
                    created_from_dashboard=True,
                    must_change_password=True,
                )
                
                # Use staff_id as temporary password
                admin.password = make_password(staff_id)
                admin.save(update_fields=['password'])
                
                # Add user to Admin group
                admin.groups.add(Group.objects.get(name='Admin'))

                messages.success(request, 'Admin created successfully!')
        except Exception as e:
            logger.error(f"Error creating admin: {e}")
            messages.error(request, 'Error creating admin. Please try again.')
        
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class UserUpdateView(PermissionRequiredMixin, View):
    permission_required = 'accounts.change_admin'
    @method_decorator(MustLogin)
    def post(self,request):
        id = request.POST.get('user_id')
        title = request.POST.get('title')
        # accept legacy keys but work with other_name + surname
        other_name = request.POST.get('other_name') or request.POST.get('first_name')
        surname = request.POST.get('surname') or request.POST.get('last_name')
        email = request.POST.get('email')
        is_active = request.POST.get('is_active')
        gender = request.POST.get('gender')
        phone_number = request.POST.get('phone_number') or request.POST.get('phone')
        school_id = request.POST.get('school')
        college_id = request.POST.get('college')
        department_id = request.POST.get('department')
        
        user = User.objects.get(id=id)
        if user.email != email:
            user.email = email
        # remove first_name field handling; update other_name and surname
        if user.other_name != other_name:
            user.other_name = other_name
        if getattr(user, 'surname', None) != surname:
            user.surname = surname
            
        if user.title != title:
            user.title = title
        
        if user.gender != gender:
            user.gender = gender
            
        if user.phone_number != phone_number:
            user.phone_number = phone_number
            
        if user.school_id != (school_id if school_id else None):
            user.school_id = school_id if school_id else None
            
        if user.college_id != (college_id if college_id else None):
            user.college_id = college_id if college_id else None
            
        if user.department_id != (department_id if department_id else None):
            user.department_id = department_id if department_id else None
            
        if user.is_active != is_active:
            user.is_active = is_active
            
        user.save()
        messages.success(request, 'Admin updated successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
        
class AdminDeleteView(PermissionRequiredMixin, View):
    permission_required = 'accounts.delete_admin'
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        admin_id = kwargs.get('admin_id')
        admin = User.objects.get(id=admin_id)
        admin.delete()
        messages.success(request, 'Admin deleted successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class MemberCreateView(PermissionRequiredMixin, View):
    permission_required = 'accounts.add_member'
    password = ""
    @method_decorator(MustLogin)
    def post(self, request):
        title = request.POST.get('title')
        # prefer other_name + surname; accept legacy first_name/last_name
        other_name = request.POST.get('other_name') or request.POST.get('first_name')
        surname = request.POST.get('surname') or request.POST.get('last_name')
        gender = request.POST.get('gender')
        email = request.POST.get('email')
        phone_number = request.POST.get('phone_number') or request.POST.get('phone')
        school_id = request.POST.get('school')
        college_id = request.POST.get('college')
        department_id = request.POST.get('department')
        staff_id = request.POST.get('staff_id', '').strip()

        # Validate staff_id
        if not staff_id:
            messages.error(request, 'Staff ID is required!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Check if staff_id already exists
        if User.objects.filter(staff_id=staff_id).exists():
            messages.error(request, 'Staff ID already exists. Please use a different Staff ID.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        member_exists = User.objects.filter(email=email).exists()
        if member_exists:
            messages.error(request, 'Member already exists!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        try:
            with transaction.atomic():
                # Create user
                member = User.objects.create(
                    title=title,
                    other_name=other_name,
                    surname=surname,
                    gender=gender,
                    email=email,
                    phone_number=phone_number,
                    school_id=school_id if school_id else None,
                    college_id=college_id if college_id else None,
                    department_id=department_id if department_id else None,
                    staff_id=staff_id,
                    created_by=request.user,
                    created_from_dashboard=True,
                    must_change_password=True,
                )
                
                # Use staff_id as temporary password
                member.password = make_password(staff_id)
                member.save(update_fields=['password'])
                
                # Add user to Member group
                member.groups.add(Group.objects.get(name='Member'))

                messages.success(request, 'Member created successfully!')
        except Exception as e:
            logger.error(f"Error creating member: {e}")
            messages.error(request, 'Error creating member. Please try again.')
        
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
class MemberDeleteView(PermissionRequiredMixin, View):
    permission_required = 'accounts.delete_member'
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        member_id = kwargs.get('member_id')
        member = User.objects.get(id=member_id)
        member.delete()
        messages.success(request, 'Member deleted successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
            

class UploadAdminData(PermissionRequiredMixin, View):
    permission_required = 'accounts.add_admin'
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
        
class UploadMemberData(PermissionRequiredMixin, View):
    permission_required = 'accounts.add_member'
    @method_decorator(MustLogin)
    def post(self, request, *args, **kwargs):
        excel_file = request.FILES.get('excel')
        csv_file = request.FILES.get('csv')

        upload = excel_file or csv_file
        if not upload:
            messages.error(request, 'No file uploaded.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

        # Always process asynchronously to avoid long-running requests/timeouts.
        ext = os.path.splitext(upload.name)[1].lower()
        safe_ext = ext if ext in {'.csv', '.xlsx', '.xls'} else ''
        rel_dir = 'bulk_uploads'
        rel_name = f"{uuid.uuid4().hex}{safe_ext}"
        rel_path = os.path.join(rel_dir, rel_name)

        saved_path = default_storage.save(rel_path, ContentFile(upload.read()))
        task = import_members_from_upload.delay(saved_path, uploaded_by_user_id=request.user.id)

        messages.success(
            request,
            f'Upload received. Import is running in the background (task id: {task.id}). '
            'You can refresh the Members page in a minute to see new members.'
        )
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


class OrgReferenceCSVView(PermissionRequiredMixin, View):
    """Download a reference CSV of School/College/Department combos."""

    permission_required = 'accounts.view_member'

    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="org_units_reference.csv"'

        writer = csv.writer(response)
        writer.writerow(['School', 'College', 'Department'])

        departments = (
            Department.objects.select_related('college__school')
            .order_by('college__school__name', 'college__name', 'name')
        )

        for dept in departments:
            school_name = dept.college.school.name if dept.college and dept.college.school else ''
            college_name = dept.college.name if dept.college else ''
            writer.writerow([school_name, college_name, dept.name])

        return response

class MemberListView(PermissionRequiredMixin, View):
    permission_required = 'accounts.view_member'
    template_name = 'dashboard_pages/members.html'
    @method_decorator(MustLogin)
    def get(self, request):
        users_qs = (
            User.objects.filter(groups__name='Member')
            .select_related('department', 'college', 'school')
            .order_by('surname', 'other_name')
            .only(
                'id', 'title', 'surname', 'other_name', 'gender', 'email', 'phone_number',
                'department__name', 'college__name', 'school__name'
            )
        )

        paginator = Paginator(users_qs, 50)
        page = request.GET.get('page')
        try:
            users_page = paginator.page(page)
        except PageNotAnInteger:
            users_page = paginator.page(1)
        except EmptyPage:
            users_page = paginator.page(paginator.num_pages)
        
        # Fetch document counts
        total_documents = Document.objects.filter(category='internal').count()
        total_external_documents = Document.objects.filter(category='external').count()
        
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        # Prepare context
        context = {
            # Keep legacy key for any includes expecting `users`
            'users': users_page,
            'total_documents': total_documents,
            'total_external_documents': total_external_documents,
            'notifications': notifications,
            'notification_count': notification_count,
            'page_obj': users_page,
            'has_add_permission': request.user.has_perm('accounts.add_member'),
            'has_change_permission': request.user.has_perm('accounts.change_member'),
            'has_delete_permission': request.user.has_perm('accounts.delete_member'),
            'schools': School.objects.all(),
            'colleges': College.objects.all(),
            'departments': Department.objects.all(),
        }
        
        # Render the template
        return render(request, self.template_name, context)

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(MustLogin, name='dispatch')
class CheckStaffIdView(View):
    """AJAX endpoint to check if staff_id is available."""
    
    def get(self, request):
        """Handle GET requests (for Parsley remote validator)."""
        staff_id = request.GET.get('staff_id', '').strip()
        return self._check_staff_id(staff_id)
    
    def post(self, request):
        """Handle POST requests."""
        staff_id = request.POST.get('staff_id', '').strip()
        return self._check_staff_id(staff_id)
    
    def _check_staff_id(self, staff_id):
        """Common logic for checking staff_id availability."""
        if not staff_id:
            return JsonResponse({'available': False, 'message': 'Staff ID is required'}, status=200)
        
        # Validate format (4-20 digits)
        import re
        if not re.match(r'^[0-9]{4,20}$', staff_id):
            return JsonResponse({
                'available': False, 
                'message': 'Staff ID must be 4-20 digits only'
            }, status=200)
        
        exists = User.objects.filter(staff_id=staff_id).exists()

        # Parsley treats non-true-ish responses as invalid, so return simple booleans
        if exists:
            return HttpResponse('false', status=200)

        return HttpResponse('true', status=200)


@method_decorator(MustLogin, name='dispatch')
class MemberSearchView(View):
    """AJAX endpoint for Select2 member search."""

    def get(self, request):
        term = request.GET.get('q', '').strip()

        qs = User.objects.all()
        if term:
            qs = qs.filter(
                Q(other_name__icontains=term)
                | Q(surname__icontains=term)
                | Q(email__icontains=term)
                | Q(staff_id__icontains=term)
            )

        qs = qs.order_by('surname', 'other_name')[:20]

        results = [
            {
                'id': user.id,
                'text': f"{user.get_full_name()} ({user.staff_id or 'No Staff ID'})",
            }
            for user in qs
        ]

        return JsonResponse({'results': results})
