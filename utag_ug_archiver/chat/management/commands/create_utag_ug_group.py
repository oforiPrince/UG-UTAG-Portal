"""
Management command to create the UTAG UG group and add all members.

Usage:
    python manage.py create_utag_ug_group
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.contrib.auth import get_user_model

from chat.models import ChatGroup, GroupMembership


class Command(BaseCommand):
    help = 'Create the UTAG UG group, add all users, and promote executives to admins.'

    def handle(self, *args, **options):
        User = get_user_model()

        creator = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.filter(is_staff=True).first()
            or User.objects.first()
        )

        if not creator:
            self.stdout.write(self.style.ERROR('No users found. Please create a user first.'))
            return

        group_name = 'UTAG UG'

        with transaction.atomic():
            group, created = ChatGroup.objects.get_or_create(
                name=group_name,
                defaults={'created_by': creator},
            )

            if not group.created_by_id:
                group.created_by = creator
                group.save(update_fields=['created_by'])

            exec_ids = set(
                User.objects.filter(
                    Q(is_active_executive=True)
                    | Q(groups__name='Executive')
                    | Q(executive_position__isnull=False)
                ).values_list('id', flat=True)
            )

            created_memberships = 0
            promoted_admins = 0

            for user in User.objects.all():
                membership, created_membership = GroupMembership.objects.get_or_create(
                    group=group,
                    user=user,
                    defaults={'added_by': creator, 'is_admin': user.id in exec_ids},
                )
                if created_membership:
                    created_memberships += 1
                if user.id in exec_ids and not membership.is_admin:
                    membership.is_admin = True
                    membership.save(update_fields=['is_admin'])
                    promoted_admins += 1

        self.stdout.write(self.style.SUCCESS('✓ UTAG UG group ready'))
        self.stdout.write(f'Group ID: {group.id}')
        self.stdout.write(f'Total members: {group.members.count()}')
        self.stdout.write(f'New memberships added: {created_memberships}')
        self.stdout.write(f'Admins promoted: {promoted_admins}')
