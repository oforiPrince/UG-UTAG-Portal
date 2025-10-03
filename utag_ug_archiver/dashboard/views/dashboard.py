from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import PermissionRequiredMixin
from accounts.models import User
from dashboard.models import Event, Document, Announcement, News, Notification

from adverts.models import Advertisement
from utag_ug_archiver.utils.decorators import MustLogin

class DashboardView(PermissionRequiredMixin, View):
    template_name = 'dashboard_pages/dashboard.html'
    permission_required = 'accounts.view_dashboard'
    
    @method_decorator(MustLogin)
    def get(self, request):
        # Counts
        total_documents = Document.objects.filter(category='internal').count()
        total_external_documents = Document.objects.filter(category='external').count()
        # get executives, members, admins, and secretaries
        total_executives = User.objects.filter(groups__name='Executive', is_active_executive=True).count()
        total_members = User.objects.filter(groups__name='Member').count()
        total_admins = User.objects.filter(groups__name='Admin').count()
        active_adverts = Advertisement.objects.filter(status='ACTIVE').order_by('-created_at')[:5]

        # User group membership
        user_groups = request.user.groups.values_list('name', flat=True)
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        # Get recent documents, events, and news
        published_events = Event.objects.filter(is_published=True).order_by('-created_at')[:5]
        published_news = News.objects.filter(is_published=True).order_by('-created_at')[:5]
        recent_added_documents = Document.objects.all().order_by('-created_at')[:5]
        
        context = {
            'total_documents': total_documents,
            'total_external_documents': total_external_documents,
            'total_executives': total_executives,
            'total_members': total_members,
            'total_admins': total_admins,
            'published_events': published_events,
            'published_news': published_news,
            'recent_added_documents': recent_added_documents,
            'notification_count': notification_count,
            'notifications': notifications,
            'active_adverts': active_adverts,
            'is_admin': 'Admin' in user_groups,
            'is_executive': 'Executive' in user_groups,
            'is_member': 'Member' in user_groups,
        }
        print(context)
        return render(request, self.template_name, context)