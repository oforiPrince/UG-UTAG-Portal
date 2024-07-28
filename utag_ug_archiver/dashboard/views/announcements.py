from django.shortcuts import redirect, render, get_object_or_404
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.db.models import Q

from dashboard.models import Announcement, Notification
from utag_ug_archiver.utils.decorators import MustLogin
from django.contrib.auth.models import Group

class AnnouncementsView(View):
    template_name = 'dashboard_pages/announcements.html'

    def get(self, request):
        user = request.user
        user_groups = user.groups.values_list('name', flat=True)  # Get names of the user's groups

        if 'Admin' in user_groups:
            announcements = Announcement.objects.all().order_by('-created_at')
        elif 'Executive' in user_groups or 'Secretary' in user_groups:
            announcements = Announcement.objects.filter(
                Q(target='everyone') | Q(target_groups__in=user.groups.all())
            ).exclude(Q(status='DRAFT') & ~Q(created_by=user)).distinct()
        else:
            announcements = Announcement.objects.filter(
                Q(target='everyone') | Q(target_groups__in=user.groups.all())
            ).exclude(Q(status='DRAFT') & ~Q(created_by=user)).distinct()

         # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        context = {
            'announcements': announcements,
            'notification_count': notification_count,
            'notifications': notifications
        }
        return render(request, self.template_name, context)


class AnnouncementCreateUpdateView(View):
    template_name = 'dashboard_pages/forms/create_update_announcement.html'

    def get(self, request, announcement_id=None):
         # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        if announcement_id:
            announcement = Announcement.objects.get(id=announcement_id)
            initial_data = {
                'title': announcement.title,
                'content': announcement.content,
                'status': announcement.status,
                'target': announcement.target,
                'target_groups': announcement.target_groups.values_list('id', flat=True)
            }
        else:
            initial_data = {
                'status': 'DRAFT',
                'target': 'everyone',
                'target_groups': [],  # Default empty list
            }

        context = {
            'initial_data': initial_data,
            'all_groups': Group.objects.all(),
            
            'notification_count': notification_count,
            'notifications': notifications
        }
        return render(request, self.template_name, context)

    def post(self, request, announcement_id=None):
        user = request.user
        title = request.POST.get('title')
        content = request.POST.get('content')
        target = request.POST.get('target')
        status = request.POST.get('status')
        target_groups_ids = request.POST.getlist('target_groups')  # List of selected group IDs

        if announcement_id:
            announcement = Announcement.objects.get(id=announcement_id)
            announcement.title = title
            announcement.content = content
            announcement.target = target
            announcement.status = status
            announcement.target_groups.set(Group.objects.filter(id__in=target_groups_ids))
            announcement.save()
            messages.info(request, "Announcement Updated Successfully")
        else:
            announcement = Announcement.objects.create(
                title=title,
                content=content,
                target=target,
                status=status,
                created_by=user
            )
            announcement.save()
            if announcement.target == 'specific_groups':
                announcement.target_groups.set(Group.objects.filter(id__in=target_groups_ids))
            announcement.save()
            
            # Send email to users
            # if announcement.status == 'PUBLISHED':
            #     send_announcement_email(announcement)
            
            messages.info(request, "Announcement Created Successfully")

        return redirect('dashboard:announcements')


class AnnouncementDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, announcement_id):
        announcement = get_object_or_404(Announcement, id=announcement_id)
        announcement.delete()
        messages.success(request, 'Announcement deleted successfully')
        return redirect('dashboard:announcements')
