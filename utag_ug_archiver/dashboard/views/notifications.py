from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from dashboard.models import Notification

from utag_ug_archiver.utils.decorators import MustLogin

class NotificationsView(View):
    template_name = 'dashboard_pages/notifications.html'

    @method_decorator(MustLogin)
    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        context = {
            'notifications': notifications
        }
        return render(request, self.template_name, context)
    
class NotificationReadView(View):
    @method_decorator(MustLogin)
    def get(self, request, notification_id):
        notification = Notification.objects.get(id=notification_id)
        notification.status = 'READ'
        notification.save()
        messages.success(request, 'Notification marked as read.')
        return redirect('dashboard:notifications')
    
class NotificationDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, notification_id):
        notification = Notification.objects.get(id=notification_id)
        notification.delete()
        messages.success(request, 'Notification deleted.')
        return redirect('dashboard:notifications')