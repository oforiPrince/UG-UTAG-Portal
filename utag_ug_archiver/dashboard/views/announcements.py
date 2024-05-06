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