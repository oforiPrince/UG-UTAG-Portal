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
            announcement_count = Announcement.objects.filter(status='PUBLISHED', target_group='EXECUTIVES').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED', target_group='EXECUTIVES').order_by('-created_at')[:3]
        elif request.user.is_member:
            announcement_count = Announcement.objects.filter(status='PUBLISHED', target_group='MEMBERS').count()
            new_announcements = Announcement.objects.filter(status='PUBLISHED', target_group='MEMBERS').order_by('-created_at')[:3]
        context = {
            'announcements' : announcements,
            'announcement_count' : announcement_count,
            'new_announcements' : new_announcements
        }
        return render(request, self.template_name, context)
    
class AnnouncementCreateView(View):    
    @method_decorator(MustLogin)
    def post(self, request):
        title = request.POST.get('title')
        content = request.POST.get('content')
        target_group = request.POST.get('target_group')
        status = request.POST.get('status')
        created_by = request.user
        announcement = Announcement.objects.create(
            title = title,
            content = content,
            target_group = target_group,
            status = status,
            created_by = created_by
        )
        messages.success(request, 'Announcement added successfully')
        return redirect('dashboard:announcements')
    
class AnnouncementUpdateView(View):    
    @method_decorator(MustLogin)
    def post(self, request):
        announcement_id = request.POST.get('announcement_id')
        title = request.POST.get('title')
        content = request.POST.get('content')
        target_group = request.POST.get('target_group')
        status = request.POST.get('status')
        announcement = Announcement.objects.get(id=announcement_id)
        announcement.title = title
        announcement.content = content
        announcement.target_group = target_group
        announcement.status = status
        announcement.save()
        messages.success(request, 'Announcement updated successfully')
        return redirect('dashboard:announcements')
    
class AnnouncementDeleteView(View):    
    @method_decorator(MustLogin)
    def get(self, request, announcement_id):
        announcement = Announcement.objects.get(id=announcement_id)
        announcement.delete()
        messages.success(request, 'Announcement deleted successfully')
        return redirect('dashboard:announcements')