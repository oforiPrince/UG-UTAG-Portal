from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import PermissionRequiredMixin
from accounts.models import User
from dashboard.models import Event, Document, Announcement, News, Notification
from django.db import models
from django.utils import timezone
from datetime import timedelta

from adverts.models import Ad
from utag_ug_archiver.utils.decorators import MustLogin

class DashboardView(PermissionRequiredMixin, View):
    template_name = 'dashboard_pages/dashboard.html'
    permission_required = 'accounts.view_dashboard'
    
    @method_decorator(MustLogin)
    def get(self, request):
        # Counts
        total_documents = Document.objects.filter(category='internal').count()
        total_external_documents = Document.objects.filter(category='external').count()
        total_announcements = Announcement.objects.filter(status='PUBLISHED').count()
        
        # Calculate dynamic percentages for last month comparison
        now = timezone.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        last_month_end = current_month_start - timedelta(seconds=1)
        
        # Current month counts
        current_month_documents = Document.objects.filter(
            category='internal', 
            created_at__gte=current_month_start
        ).count()
        current_month_external = Document.objects.filter(
            category='external', 
            created_at__gte=current_month_start
        ).count()
        current_month_announcements = Announcement.objects.filter(
            status='PUBLISHED',
            created_at__gte=current_month_start
        ).count()
        
        # Last month counts
        last_month_documents = Document.objects.filter(
            category='internal', 
            created_at__gte=last_month_start, 
            created_at__lte=last_month_end
        ).count()
        last_month_external = Document.objects.filter(
            category='external', 
            created_at__gte=last_month_start, 
            created_at__lte=last_month_end
        ).count()
        last_month_announcements = Announcement.objects.filter(
            status='PUBLISHED',
            created_at__gte=last_month_start, 
            created_at__lte=last_month_end
        ).count()
        
        # Calculate percentage changes
        def calculate_percentage_change(current, previous):
            if previous == 0:
                return current * 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 1)
        
        documents_percentage = calculate_percentage_change(current_month_documents, last_month_documents)
        external_documents_percentage = calculate_percentage_change(current_month_external, last_month_external)
        announcements_percentage = calculate_percentage_change(current_month_announcements, last_month_announcements)

        # get executives, members, admins, and secretaries
        total_executives = User.objects.filter(groups__name='Executive', is_active_executive=True).count()
        total_members = User.objects.filter(groups__name='Member').count()
        total_admins = User.objects.filter(groups__name='Admin').count()
        # Use new Ad model; show active ads
        active_adverts = Ad.objects.filter(active=True).order_by('-created_at')[:5]

        # User group membership
        user_groups = request.user.groups.values_list('name', flat=True)
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        # Get recent documents, events, and news
        published_events = Event.objects.filter(is_published=True).order_by('-created_at')[:5]
        published_news = News.objects.filter(is_published=True).order_by('-created_at')[:5]

        # Get recent documents based on user role
        if request.user.is_superuser or 'Admin' in user_groups:
            # Superusers and Admins see all documents
            recent_added_documents = Document.objects.all().order_by('-created_at')[:5]
        else:
            # All other users see documents visible to everyone or to their groups
            user_groups_queryset = request.user.groups.all()
            recent_added_documents = Document.objects.filter(
                models.Q(visibility='everyone') | 
                models.Q(visibility='selected_groups', visible_to_groups__in=user_groups_queryset)
            ).distinct().order_by('-created_at')[:5]
        
        context = {
            'total_documents': total_documents,
            'total_external_documents': total_external_documents,
            'total_announcements': total_announcements,
            'total_executives': total_executives,
            'total_members': total_members,
            'total_admins': total_admins,
            'documents_percentage': documents_percentage,
            'external_documents_percentage': external_documents_percentage,
            'announcements_percentage': announcements_percentage,
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