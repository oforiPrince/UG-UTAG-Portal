"""
Management command to create department and school communication groups.

Usage:
    python manage.py create_communication_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from accounts.models import User, Department, School


class Command(BaseCommand):
    help = 'Create communication groups for departments and schools, and assign users to them'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting group creation...'))
        
        # Track statistics
        dept_groups_created = 0
        dept_groups_existing = 0
        school_groups_created = 0
        school_groups_existing = 0
        dept_memberships_added = 0
        school_memberships_added = 0

        # Create department groups
        self.stdout.write('\n=== Creating Department Groups ===')
        departments = Department.objects.all()
        
        for dept in departments:
            group_name = f"Department: {dept.name}"
            group, created = Group.objects.get_or_create(name=group_name)
            
            if created:
                dept_groups_created += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created group: {group_name}'))
            else:
                dept_groups_existing += 1
                self.stdout.write(f'  Group already exists: {group_name}')
            
            # Add all users from this department to the group
            users_in_dept = User.objects.filter(department=dept)
            added_count = 0
            
            for user in users_in_dept:
                if not user.groups.filter(id=group.id).exists():
                    user.groups.add(group)
                    added_count += 1
                    dept_memberships_added += 1
            
            if added_count > 0:
                self.stdout.write(f'  → Added {added_count} users to {group_name}')

        # Create school groups
        self.stdout.write('\n=== Creating School Groups ===')
        schools = School.objects.all()
        
        for school in schools:
            group_name = f"School: {school.name}"
            group, created = Group.objects.get_or_create(name=group_name)
            
            if created:
                school_groups_created += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created group: {group_name}'))
            else:
                school_groups_existing += 1
                self.stdout.write(f'  Group already exists: {group_name}')
            
            # Add all users from this school to the group
            users_in_school = User.objects.filter(school=school)
            added_count = 0
            
            for user in users_in_school:
                if not user.groups.filter(id=group.id).exists():
                    user.groups.add(group)
                    added_count += 1
                    school_memberships_added += 1
            
            if added_count > 0:
                self.stdout.write(f'  → Added {added_count} users to {group_name}')

        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('\n✓ Group Creation Complete!\n'))
        self.stdout.write(f'Department Groups Created: {dept_groups_created}')
        self.stdout.write(f'Department Groups Already Existed: {dept_groups_existing}')
        self.stdout.write(f'Department Memberships Added: {dept_memberships_added}')
        self.stdout.write(f'\nSchool Groups Created: {school_groups_created}')
        self.stdout.write(f'School Groups Already Existed: {school_groups_existing}')
        self.stdout.write(f'School Memberships Added: {school_memberships_added}')
        self.stdout.write('\n' + '='*60)
