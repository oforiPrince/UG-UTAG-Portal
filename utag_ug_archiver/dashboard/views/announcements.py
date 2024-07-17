from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect

from django.db.models import Q


from dashboard.models import Announcement

from utag_ug_archiver.utils.decorators import MustLogin

class AnnouncementsView(View):
    template_name = 'dashboard_pages/announcements.html'
    def get(self, request):
        if request.user.is_superuser or request.user.is_admin:
            announcements = Announcement.objects.all().order_by('-created_at')
        elif request.user.is_secretary or request.user.is_executive:
            announcements = Announcement.objects.filter(target_group='ALL').exclude(
    Q(status='DRAFT') & ~Q(created_by=request.user)
)
        else:
            announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='EXECUTIVES')
        announcement_count = 0
        if request.user.is_admin:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif request.user.is_secretary or request.user.is_executive:
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='MEMBERS').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='MEMBERS').order_by('-created_at')[:3]
        elif request.user.is_member:
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='EXECUTIVES').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='EXECUTIVES').order_by('-created_at')[:3]
        context = {
            'announcements' : announcements,
            'announcement_count' : announcement_count,
            'new_announcements' : new_announcements
        }
        return render(request, self.template_name, context)
    
class AnnouncementCreateUpdateView(View):
    template_name = 'dashboard_pages/forms/create_update_announcement.html'

    @method_decorator(MustLogin)
    def get(self, request, announcement_id=None):
        if announcement_id:
            announcement = Announcement.objects.get(id=announcement_id)
            initial_data = {
                'title': announcement.title,
                'content': announcement.content,
                'target_group': announcement.target_group,
                'status': announcement.status,
            }
        else:
            initial_data = {
                'status': 'DRAFT',
                'target_group': 'ALL',
            }
        return render(request, self.template_name, {'initial_data': initial_data})

    @method_decorator(MustLogin)
    def post(self, request, announcement_id=None):
        user = request.user
        title = request.POST.get('title')
        content = request.POST.get('content')
        target_group = request.POST.get('target_group')
        status = request.POST.get('status')

        if announcement_id:
            announcement = Announcement.objects.get(id=announcement_id)
            announcement.title = title
            announcement.content = content
            announcement.target_group = target_group
            announcement.status = status
            announcement.save()
            messages.info(request, "Announcement Updated Successfully")
        else:
            announcement = Announcement.objects.create(
                title=title,
                content=content,
                target_group=target_group,
                status=status,
                created_by=user
            )
            announcement.save()
            messages.info(request, "Announcement Created Successfully")

        return redirect('dashboard:announcements')
    
class AnnouncementDeleteView(View):    
    @method_decorator(MustLogin)
    def get(self, request, announcement_id):
        announcement = Announcement.objects.get(id=announcement_id)
        announcement.delete()
        messages.success(request, 'Announcement deleted successfully')
        return redirect('dashboard:announcements')