from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from dashboard.models import Event, News, Announcement, Document
from accounts.models import User
from adverts.models import Advertisement, AdvertPlan, Advertiser, Payment

class Command(BaseCommand):
    help = 'Create groups and assign permissions'

    def handle(self, *args, **kwargs):
        # Define the groups and their permissions
        groups_permissions = {
            'Admin': [
                'view_dashboard',
                'view_admins',
                'view_members',
                'view_executives',
                'add_user', 'change_user', 'delete_user', 'view_user',
                'add_event', 'change_event', 'delete_event', 'view_event',
                'add_news', 'change_news', 'delete_news', 'view_news',
                'add_announcement', 'change_announcement', 'delete_announcement', 'view_announcement',
                'add_document', 'change_document', 'delete_document', 'view_document',
                'add_advertiser', 'change_advertiser', 'delete_advertiser', 'view_advertiser',
                'add_advertisement', 'change_advertisement', 'delete_advertisement', 'view_advertisement',
                'add_advertplan', 'change_advertplan', 'delete_advertplan', 'view_advertplan',
                'add_payment', 'change_payment', 'delete_payment', 'view_payment',
            ],
            'Secretary': [
                'view_dashboard',
                'view_event', 'view_news', 'view_announcement', 'view_document',
                'view_advertisement', 'view_advertiser', 'view_payment',
            ],
            'Executive': [
                'view_dashboard',
                'view_members',
                'view_event', 'view_news', 'view_announcement',
                'view_advertisement', 'view_advertiser',
            ],
            'Member': [
                'view_dashboard',
                'view_event', 'view_news',
            ],
            'Committee Member': [
                'view_dashboard',
                'view_event', 'view_news',
            ],
        }

        for group_name, permissions in groups_permissions.items():
            # Create or get the group
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {group_name}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Group already exists: {group_name}'))

            for perm_codename in permissions:
                try:
                    # Get the permission by its codename
                    perm = Permission.objects.get(codename=perm_codename)
                    # Add the permission to the group
                    group.permissions.add(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f'Permission not found: {perm_codename}'))

            self.stdout.write(self.style.SUCCESS(f'Assigned permissions to group: {group_name}'))

        self.stdout.write(self.style.SUCCESS('Groups and permissions setup complete'))
