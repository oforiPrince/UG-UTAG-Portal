import logging
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.utils.decorators import method_decorator
from django.db.models import Q
from accounts.models import User
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
