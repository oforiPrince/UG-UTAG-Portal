from celery import shared_task
from datetime import datetime
from django.utils import timezone
from dashboard.models import Event
from adverts.models import Ad

@shared_task
def update_event_statuses():
    """Update event statuses based on current date/time"""
    now = timezone.now()
    
    # Update upcoming events that have started
    Event.objects.filter(
        status='upcoming',
        start_date__lte=now.date(),
        start_time__lte=now.time()
    ).update(status='ongoing')
    
    # Update ongoing events that have ended
    for event in Event.objects.filter(status='ongoing'):
        end_date = event.end_date or event.start_date
        end_time = event.end_time or datetime.time(23, 59, 59)
        
        end_datetime = timezone.make_aware(
            datetime.datetime.combine(end_date, end_time)
        )
        
        if now > end_datetime:
            event.status = 'completed'
            event.save()
    
    return f"Event statuses updated at {now}"

@shared_task
def update_advert_statuses():
    """Mark expired advertisements"""
    now = timezone.now()

    # Deactivate ads that have an end datetime in the past
    expired_ads = Ad.objects.filter(active=True, end__isnull=False, end__lt=now)
    count = expired_ads.count()
    expired_ads.update(active=False)

    return f"{count} adverts deactivated"