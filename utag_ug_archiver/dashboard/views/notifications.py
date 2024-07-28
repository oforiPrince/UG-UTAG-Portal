from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from dashboard.models import Notification
from django.http import JsonResponse
from utag_ug_archiver.utils.decorators import MustLogin
from django.utils.safestring import mark_safe

class NotificationsView(View):
    template_name = 'dashboard_pages/notifications.html'

    @method_decorator(MustLogin)
    def get(self, request):
        user_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
         # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        context = {
            'notifications': notifications,
            'notification_count': notification_count,
            'user_notifications': user_notifications
        }
        return render(request, self.template_name, context)
    
class NotificationReadView(View):
    @method_decorator(MustLogin)
    def get(self, request, notification_id):
        notification = Notification.objects.get(id=notification_id)
        notification.status = 'READ'
        notification.save()
        messages.success(request, 'Notification marked as read')
        return redirect('dashboard:notifications')
    
class NotificationDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, notification_id):
        notification = Notification.objects.get(id=notification_id)
        notification.delete()
        messages.success(request, 'Notification deleted successfully')
        return redirect('dashboard:notifications')
    
class NotificationDetailsView(View):

    def get(self, request, notification_id):
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.status = 'READ'
        notification.save()
        data = {
        'announcement_title': notification.announcement.title,
        'announcement_content': mark_safe(notification.announcement.content),
        'status': notification.status,
        'created_at': notification.created_at.strftime('%d M Y, %H:%M'),
        }

        return JsonResponse(data)