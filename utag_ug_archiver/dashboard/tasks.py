from celery import shared_task
from datetime import datetime
from django.utils import timezone
from dashboard.models import Event
from adverts.models import Advertisement

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
    today = timezone.now().date()
    
    # Find published ads that have passed their end date
    expired_ads = Advertisement.objects.filter(
        status='PUBLISHED', 
        end_date__lt=today
    )
    
    count = expired_ads.count()
    expired_ads.update(status='EXPIRED')
    
    return f"{count} advertisements marked as expired"