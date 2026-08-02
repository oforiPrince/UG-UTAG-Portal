import logging
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.utils.decorators import method_decorator
from django.db.models import Q
from accounts.models import User, Department, School, College
from utag_ug_archiver.utils.decorators import MustLogin

logger = logging.getLogger(__name__)


class MembersDataTableAPIView(PermissionRequiredMixin, View):
    """Server-side API for DataTables member list.
    
    Accepts DataTables parameters (draw, start, length, search, order)
    and returns paginated, sorted, filtered members as JSON.
    """
    permission_required = 'accounts.view_member'
    
    @method_decorator(MustLogin)
    def get(self, request):
        try:
            # DataTables parameters
            draw = int(request.GET.get('draw', 1))
            start = int(request.GET.get('start', 0))
            length = int(request.GET.get('length', 50))
            search_value = request.GET.get('search[value]', '').strip()
            
            # Order parameters (DataTables sends order[0][column] and order[0][dir])
            order_column = int(request.GET.get('order[0][column]', 1))  # default to column 1 (Title)
            order_dir = request.GET.get('order[0][dir]', 'asc')  # asc or desc
            
            # Column mapping: match the table columns (academic focus)
            columns = [
                'id',                  # 0: #
                'surname',             # 1: Surname
                'other_name',          # 2: Other Name(s)
                'academic_rank',       # 3: Academic Rank
                'email',               # 4: Email
            ]
            
            # Build queryset
            queryset = (
                User.objects.filter(groups__name='Member')
                .only(
                    'id', 'surname', 'other_name', 'academic_rank', 'email'
                )
            )
            
            # Apply search filter
            if search_value:
                queryset = queryset.filter(
                    Q(surname__icontains=search_value)
                    | Q(other_name__icontains=search_value)
                    | Q(email__icontains=search_value)
                    | Q(academic_rank__icontains=search_value)
                )
            
            # Get total count before pagination
            total_count = queryset.count()
            
            # Apply ordering
            if order_column < len(columns):
                order_by = columns[order_column]
                if order_dir.lower() == 'desc':
                    order_by = f'-{order_by}'
                queryset = queryset.order_by(order_by)
            else:
                queryset = queryset.order_by('surname', 'other_name')
            
            # Apply pagination
            end = start + length
            members = queryset[start:end]
            
            # Build response data
            data = []
            for i, member in enumerate(members, start=start + 1):
                data.append([
                    i,  # Row number
                    (member.surname or '').title(),
                    (member.other_name or '').title(),
                    (member.academic_rank or '').title(),
                    member.email or '',
                    str(member.id),  # ID for actions (hidden in table, used by JS)
                ])
            
            return JsonResponse({
                'draw': draw,
                'recordsTotal': total_count,
                'recordsFiltered': total_count if not search_value else queryset.count(),
                'data': data,
            })
        except Exception as e:
            logger.error(f"MembersDataTableAPIView error: {e}", exc_info=True)
            return JsonResponse({
                'draw': 1,
                'recordsTotal': 0,
                'recordsFiltered': 0,
                'data': [],
                'error': str(e),
            }, status=500)


class MemberDetailAPIView(PermissionRequiredMixin, View):
    """AJAX API for fetching member details for dynamic modal loading.
    
    Returns member data as JSON to avoid rendering all modals on page load.
    """
    permission_required = 'accounts.view_member'
    
    @method_decorator(MustLogin)
    def get(self, request, member_id):
        try:
            user = User.objects.get(id=member_id, groups__name='Member')
            
            # Get groups as list
            groups = list(user.groups.values_list('name', flat=True))
            
            # Get schools, colleges, departments for dropdowns
            schools = [{'id': s.id, 'name': s.name} for s in School.objects.all()]
            colleges = [{'id': c.id, 'name': c.name} for c in College.objects.all()]
            departments = [{'id': d.id, 'name': d.name} for d in Department.objects.all()]
            
            return JsonResponse({
                'id': user.id,
                'title': user.title or '',
                'surname': user.surname or '',
                'other_name': user.other_name or '',
                'email': user.email or '',
                'phone_number': user.phone_number or '',
                'gender': user.gender or '',
                'academic_rank': user.academic_rank or '',
                'staff_id': user.staff_id or '',
                'profile_pic': user.profile_pic.url if user.profile_pic else '',
                'full_name': user.get_full_name(),
                'short_name': user.get_short_name(),
                'groups': groups,
                'department_id': user.department.id if user.department else '',
                'department_name': user.department.name if user.department else '',
                'school_id': user.school.id if user.school else '',
                'school_name': user.school.name if user.school else '',
                'college_id': user.college.id if user.college else '',
                'college_name': user.college.name if user.college else '',
                'is_active': user.is_active,
                'schools': schools,
                'colleges': colleges,
                'departments': departments,
            })
        except User.DoesNotExist:
            return JsonResponse({'error': 'Member not found'}, status=404)
        except Exception as e:
            logger.error(f"MemberDetailAPIView error: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)


class MemberPasswordResetAPIView(PermissionRequiredMixin, View):
    """API for admin to reset a member's password.
    
    Generates a temporary password and resets the user's password.
    Logs the action for audit trail.
    """
    permission_required = 'accounts.change_member'
    
    @method_decorator(MustLogin)
    def post(self, request, member_id):
        try:
            user = User.objects.get(id=member_id, groups__name='Member')
            
            # Generate a temporary password
            import uuid
            temporary_password = str(uuid.uuid4())[:12]
            
            # Set the temporary password
            user.set_password(temporary_password)
            user.must_change_password = True  # Force password change on next login
            user.save()
            
            # Log the action
            logger.info(
                f"Password reset by {request.user.get_full_name()} ({request.user.email}) "
                f"for member {user.get_full_name()} ({user.email}). "
                f"Member must change password on next login."
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Password reset successfully. Temporary password: {temporary_password}',
                'temporary_password': temporary_password,
                'member_name': user.get_full_name(),
                'member_email': user.email,
            })
        except User.DoesNotExist:
            return JsonResponse({'error': 'Member not found'}, status=404)
        except Exception as e:
            logger.error(f"MemberPasswordResetAPIView error: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)


class MemberUpdateAPIView(PermissionRequiredMixin, View):
    """API for admin to update member details.
    
    Updates member profile information like name, phone, academic rank, department, etc.
    """
    permission_required = 'accounts.change_member'
    
    @method_decorator(MustLogin)
    def post(self, request, member_id):
        try:
            user = User.objects.get(id=member_id, groups__name='Member')
            
            # Get form data
            title = request.POST.get('title')
            surname = request.POST.get('surname')
            other_name = request.POST.get('other_name')
            phone_number = request.POST.get('phone_number')
            academic_rank = request.POST.get('academic_rank')
            gender = request.POST.get('gender')
            staff_id = request.POST.get('staff_id')
            school_id = request.POST.get('school_id')
            college_id = request.POST.get('college_id')
            department_id = request.POST.get('department_id')
            
            # Update fields
            if title:
                user.title = title
            if surname:
                user.surname = surname
            if other_name:
                user.other_name = other_name
            if phone_number is not None:
                user.phone_number = phone_number
            if academic_rank:
                user.academic_rank = academic_rank
            if gender:
                user.gender = gender
            if staff_id is not None:
                user.staff_id = staff_id
            
            # Update foreign keys
            if school_id:
                try:
                    user.school = School.objects.get(id=school_id)
                except School.DoesNotExist:
                    pass
            
            if college_id:
                try:
                    user.college = College.objects.get(id=college_id)
                except College.DoesNotExist:
                    pass
            
            if department_id:
                try:
                    user.department = Department.objects.get(id=department_id)
                except Department.DoesNotExist:
                    pass
            
            user.save()
            
            # Log the action
            logger.info(
                f"Member {user.get_full_name()} ({user.email}) updated by admin {request.user.get_full_name()}"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Member {user.get_full_name()} updated successfully',
                'member_name': user.get_full_name(),
            })
        except User.DoesNotExist:
            return JsonResponse({'error': 'Member not found'}, status=404)
        except Exception as e:
            logger.error(f"MemberUpdateAPIView error: {e}", exc_info=True)
            return JsonResponse({'error': str(e)}, status=500)

