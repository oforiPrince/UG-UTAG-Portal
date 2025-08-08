import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'utag_ug_archiver.settings')

app = Celery('utag_ug_archiver')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()