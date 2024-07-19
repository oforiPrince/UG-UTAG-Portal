from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import PermissionRequiredMixin




from accounts.models import User
from dashboard.models import Executive, Event, Document, Announcement, News

from adverts.models import Advertisement
from utag_ug_archiver.utils.decorators import MustLogin

class DashboardView(PermissionRequiredMixin,View):
    template_name = 'dashboard_pages/dashboard.html'
    permission_required = 'accounts.view_dashboard'
    
    @method_decorator(MustLogin)
    def get(self, request):
        # Count totals
        total_documents = Document.objects.filter(category='internal').count()
        total_external_documents = Document.objects.filter(category='external').count()
        total_executives = Executive.objects.filter(is_active=True).count()
        total_members = User.objects.filter(groups__name='Member').count()
        total_admins = User.objects.filter(groups__name='Admin').count()
        total_secretaries = User.objects.filter(groups__name='Secretary').count()
        active_adverts = Advertisement.objects.filter(status='ACTIVE').order_by('-created_at')[:5]

        # Check group membership and filter announcements
        user_groups = request.user.groups.values_list('name', flat=True)
        if 'Admin' in user_groups:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').count()
        elif 'Secretary' in user_groups or 'Executive' in user_groups:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='MEMBERS').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='MEMBERS').count()
        elif 'Member' in user_groups:
            new_announcements = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='EXECUTIVES').order_by('-created_at')[:3]
            announcement_count = Announcement.objects.filter(status='PUBLISHED').exclude(target_group='EXECUTIVES').count()
        else:
            new_announcements = []
            announcement_count = 0

        # Get recent documents, events, and news
        published_events = Event.objects.filter(is_published=True).order_by('-date')[:5]
        published_news = News.objects.filter(is_published=True).order_by('-created_at')[:5]
        recent_added_documents = Document.objects.all().order_by('-created_at')[:5]

        context = {
            'total_documents': total_documents,
            'total_external_documents': total_external_documents,
            'total_executives': total_executives,
            'total_members': total_members,
            'total_admins': total_admins,
            'total_secretaries': total_secretaries,
            'published_events': published_events,
            'published_news': published_news,
            'recent_added_documents': recent_added_documents,
            'announcement_count': announcement_count,
            'new_announcements': new_announcements,
            'active_adverts': active_adverts,
        }
        return render(request, self.template_name, context)