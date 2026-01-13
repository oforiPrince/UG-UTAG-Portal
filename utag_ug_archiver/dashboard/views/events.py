from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect
from datetime import date, time


from dashboard.models import Announcement, Event, Notification

from utag_ug_archiver.utils.decorators import MustLogin


#For Events and Event
class EventsView(View):
    template_name = 'dashboard_pages/events.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all events
        events = Event.objects.all()
        
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        context = {
            'events' : events,
            'notification_count' : notification_count,
            'notifications' : notifications
        }
        return render(request, self.template_name, context)
    
class EventCreateUpdateView(View):
    template_name = 'dashboard_pages/forms/create_update_event.html'

    @method_decorator(MustLogin)
    def get(self, request, event_id=None):
        # Get notifications
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        notification_count = Notification.objects.filter(user=request.user, status='UNREAD').count()
        
        if event_id:
            event = Event.objects.get(id=event_id)
            context = {
                'title': event.title,
                'description': event.description,
                'is_published': 'on' if event.is_published else 'off',
                'featured_image': event.featured_image,
                'venue': event.venue,
                'start_date': event.start_date,
                'end_date': event.end_date,
                'start_time': event.start_time,
                'end_time': event.end_time,
                'notifications':notifications,
                'notification_count': notification_count,
                'active_menu': 'events'
            }
        else:
            context = {
                'is_published': 'off',
                'notifications':notifications,
                'notification_count': notification_count,
                'active_menu': 'events'
            }
        return render(request, self.template_name, {'context': context})

    @method_decorator(MustLogin)
    def post(self, request, event_id=None):
        user = request.user
        title = request.POST.get('title')
        description = request.POST.get('description')
        venue = request.POST.get('venue')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        start_time_str = request.POST.get('start_time')
        end_time_str = request.POST.get('end_time')
        is_published = request.POST.get('is_published')
        featured_image = request.FILES.get('image')

        # Parse dates and times
        start_date = date.fromisoformat(start_date_str) if start_date_str else None
        end_date = date.fromisoformat(end_date_str) if end_date_str else None
        start_time = time.fromisoformat(start_time_str) if start_time_str else None
        end_time = time.fromisoformat(end_time_str) if end_time_str else None

        if not start_date:
            messages.error(request, "Start date is required")
            return redirect('dashboard:create_event')

        if is_published == 'on':
            is_published = True
        else:
            is_published = False

        if event_id:
            event = Event.objects.get(id=event_id)
            event.title = title
            event.description = description
            event.is_published = is_published
            event.featured_image = featured_image
            event.venue = venue
            event.start_date = start_date
            event.end_date = end_date
            event.start_time = start_time
            event.end_time = end_time
            event.save()
            messages.info(request, "Event Updated Successfully")
        else:
            event = Event.objects.create(
                created_by=user,
                title=title,
                description=description,
                is_published=is_published,
                featured_image=featured_image,
                venue=venue,
                start_date=start_date,
                end_date=end_date,
                start_time=start_time,
                end_time=end_time,
            )
            messages.info(request, "Event Created Successfully")

        return redirect('dashboard:events')
    
class EventDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        event = Event.objects.get(id=event_id)
        event.delete()
        messages.success(request, 'Event deleted successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
