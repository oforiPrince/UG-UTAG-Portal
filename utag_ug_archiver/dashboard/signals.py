from django.db.models.signals import post_save
from django.dispatch import receiver

from dashboard.models import Announcement, Notification
from accounts.models import User

@receiver(post_save, sender=Announcement)
def create_notifications(sender, instance, **kwargs):
    if instance.target == 'everyone' and instance.status == 'PUBLISHED':
        # Create notifications for all users
        users = User.objects.all()
    elif instance.target == 'specific_groups' and instance.status == 'PUBLISHED':
        # Create notifications for users in specific groups
        users = User.objects.filter(groups__in=instance.target_groups.all()).distinct()
    
    for user in users:
        Notification.objects.get_or_create(
            user=user,
            announcement=instance
        )
