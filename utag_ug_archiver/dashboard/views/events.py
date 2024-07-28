from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect


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
                'image': event.image,
                'venue': event.venue,
                'date': event.date,
                'time': event.time,
                'notifications':notifications,
                'notification_count': notification_count
            }
        else:
            context = {
                'is_published': 'off',
                'notifications':notifications,
                'notification_count': notification_count
            }
        return render(request, self.template_name, {'context': context})

    @method_decorator(MustLogin)
    def post(self, request, event_id=None):
        user = request.user
        title = request.POST.get('title')
        description = request.POST.get('description')
        venue = request.POST.get('venue')
        date = request.POST.get('date')
        time = request.POST.get('time')
        is_published = request.POST.get('is_published')
        image = request.FILES.get('image')

        if is_published == 'on':
            is_published = True
        else:
            is_published = False

        if event_id:
            event = Event.objects.get(id=event_id)
            event.title = title
            event.description = description
            event.is_published = is_published
            event.image = image
            event.venue = venue
            event.date = date
            event.time = time
            event.save()
            messages.info(request, "Event Updated Successfully")
        else:
            event = Event.objects.create(
                created_by=user,
                title=title,
                description=description,
                is_published=is_published,
                image=image,
                venue=venue,
                date=date,
                time=time,
            )
            event.save()
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
    
