from django.core.management.base import BaseCommand
from adverts.models import Advertisement
from datetime import date

class Command(BaseCommand):
    help = 'Deactivate advertisements whose plans have expired'

    def handle(self, *args, **kwargs):
        today = date.today()
        ads_to_deactivate = Advertisement.objects.filter(
            status='PUBLISHED',
            end_date__lt=today
        )
        
        count = ads_to_deactivate.update(status='EXPIRED')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully deactivated {count} advertisements'))
