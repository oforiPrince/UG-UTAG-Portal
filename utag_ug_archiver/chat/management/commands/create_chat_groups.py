"""
Management command to create chat groups for departments and schools.

Usage:
    python manage.py create_chat_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from chat.models import ChatGroup, GroupMembership
from accounts.models import User


class Command(BaseCommand):
    help = 'Create chat groups for departments and schools based on auth groups'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting chat group creation...'))
        
        # Track statistics
        chat_groups_created = 0
        chat_groups_existing = 0
        total_memberships_added = 0
        
        # Get the system admin user or first superuser for group creation
        system_user = User.objects.filter(is_superuser=True).first()
        if not system_user:
            self.stdout.write(self.style.ERROR('No superuser found! Please create one first.'))
            return
        
        # Find all auth groups that start with "Department:" or "School:"
        self.stdout.write('\n=== Creating Chat Groups ===')
        
        for auth_group in Group.objects.filter(name__in=['Department:', 'School:']):
            prefix = auth_group.name.split(':')[0]
            
            if prefix == 'Department':
                self.stdout.write(f'\n--- Department Groups ---')
            elif prefix == 'School':
                self.stdout.write(f'\n--- School Groups ---')
        
        # Process Department groups
        dept_groups = Group.objects.filter(name__startswith='Department:')
        for auth_group in dept_groups:
            # Extract the department name from the group name
            # Format: "Department: DeptName"
            dept_name = auth_group.name.replace('Department: ', '')
            chat_group_name = f"Department: {dept_name}"
            
            chat_group, created = ChatGroup.objects.get_or_create(
                name=chat_group_name,
                defaults={'created_by': system_user}
            )
            
            if created:
                chat_groups_created += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created chat group: {chat_group_name}'))
            else:
                chat_groups_existing += 1
                self.stdout.write(f'  Chat group already exists: {chat_group_name}')
            
            # Add members from the auth group
            users = auth_group.user_set.all()
            added_count = 0
            
            for user in users:
                membership, created = GroupMembership.objects.get_or_create(
                    group=chat_group,
                    user=user,
                    defaults={'added_by': system_user}
                )
                if created:
                    added_count += 1
                    total_memberships_added += 1
            
            if added_count > 0:
                self.stdout.write(f'  → Added {added_count} members to {chat_group_name}')
            else:
                self.stdout.write(f'  → All {users.count()} members already in {chat_group_name}')
        
        # Process School groups
        school_groups = Group.objects.filter(name__startswith='School:')
        for auth_group in school_groups:
            # Extract the school name from the group name
            # Format: "School: SchoolName"
            school_name = auth_group.name.replace('School: ', '')
            chat_group_name = f"School: {school_name}"
            
            chat_group, created = ChatGroup.objects.get_or_create(
                name=chat_group_name,
                defaults={'created_by': system_user}
            )
            
            if created:
                chat_groups_created += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created chat group: {chat_group_name}'))
            else:
                chat_groups_existing += 1
                self.stdout.write(f'  Chat group already exists: {chat_group_name}')
            
            # Add members from the auth group
            users = auth_group.user_set.all()
            added_count = 0
            
            for user in users:
                membership, created = GroupMembership.objects.get_or_create(
                    group=chat_group,
                    user=user,
                    defaults={'added_by': system_user}
                )
                if created:
                    added_count += 1
                    total_memberships_added += 1
            
            if added_count > 0:
                self.stdout.write(f'  → Added {added_count} members to {chat_group_name}')
            else:
                self.stdout.write(f'  → All {users.count()} members already in {chat_group_name}')
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('\n✓ Chat Group Creation Complete!\n'))
        self.stdout.write(f'Chat Groups Created: {chat_groups_created}')
        self.stdout.write(f'Chat Groups Already Existed: {chat_groups_existing}')
        self.stdout.write(f'Total New Memberships Added: {total_memberships_added}')
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.WARNING('\nMembers can now chat in their department and school groups!'))
