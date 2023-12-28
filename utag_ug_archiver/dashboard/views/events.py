from django.shortcuts import redirect, render
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import HttpResponseRedirect


from dashboard.models import Event

from utag_ug_archiver.utils.decorators import MustLogin


#For Events and News
class EventsView(View):
    template_name = 'dashboard_pages/events.html'
    @method_decorator(MustLogin)
    def get(self, request):
        #Get all events
        events = Event.objects.all()
        context = {
            'events' : events
        }
        return render(request, self.template_name, context)
    
class EventCreateView(View):
    @method_decorator(MustLogin)
    def get(self, request):
        return render(request, self.template_name)
    
    @method_decorator(MustLogin)
    def post(self, request):
        user = request.user
        title = request.POST.get('title')
        description = request.POST.get('description')
        date = request.POST.get('date')
        time = request.POST.get('time')
        venue = request.POST.get('venue')
        is_published = request.POST.get('is_published')
        image = request.FILES.get('image')
        if is_published == 'on':
            is_published = True
        else:
            is_published = False
        event = Event.objects.create(
            created_by = user,
            title = title,
            description = description,
            date = date,
            time = time,
            venue = venue,
            is_published = is_published,
            image = image
        )
        event.save()
        messages.info(request, "Event Created Successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class EventUpdateView(View):
    @method_decorator(MustLogin)
    def get(self, request, pk):
        event = Event.objects.get(pk=pk)
        context = {
            'event' : event
        }
        return render(request, self.template_name, context)
    
    @method_decorator(MustLogin)
    def post(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        event = Event.objects.get(pk=event_id)
        title = request.POST.get('title')
        description = request.POST.get('description')
        date = request.POST.get('date')
        time = request.POST.get('time')
        venue = request.POST.get('venue')
        is_published = request.POST.get('is_published')
        image = request.FILES.get('image')
        if image:
            event.image = image
            event.save()
        event.title = title
        event.description = description
        event.date = date
        event.time = time
        event.venue = venue
        event.is_published = is_published
        event.save()
        messages.info(request, "Event Updated Successfully")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
class EventDeleteView(View):
    @method_decorator(MustLogin)
    def get(self, request, *args, **kwargs):
        event_id = kwargs.get('event_id')
        event = Event.objects.get(id=event_id)
        event.delete()
        messages.success(request, 'Event deleted successfully!')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
