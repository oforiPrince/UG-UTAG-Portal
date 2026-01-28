from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import School, College, Department
from django.contrib.auth.models import Group, Permission
from django.contrib.auth import get_user_model
from django.db.models import Count


class Command(BaseCommand):
    help = (
        'Remove UG schools, colleges and departments loaded by load_ug_data.py. '
        'This operation is destructive. Use --confirm=DELETE_UG_DATA to proceed.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            type=str,
            help='Confirmation token required to perform deletion (value: DELETE_UG_DATA)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only show what would be deleted, do not perform deletions'
        )

    def handle(self, *args, **options):
        token = options.get('confirm')
        dry_run = options.get('dry_run')

        if token != 'DELETE_UG_DATA':
            raise CommandError(
                'This command will delete data. Re-run with --confirm=DELETE_UG_DATA to proceed.'
            )

        # Dataset copied from load_ug_data.py — names must match exactly.
        data = {
            'School of Arts': {
                'colleges': {
                    'College of Humanities': [
                        'Department of English',
                        'Department of History',
                        'Department of Philosophy and Classics',
                        'Department of Religions',
                        'Department of Theatre Arts',
                    ]
                }
            },
            'School of Sciences': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Biochemistry, Cell and Molecular Biology',
                        'Department of Botany',
                        'Department of Chemistry',
                        'Department of Computer Science',
                        'Department of Earth Science',
                        'Department of Mathematics',
                        'Department of Physics',
                        'Department of Statistics',
                    ]
                }
            },
            'School of Social Sciences': {
                'colleges': {
                    'College of Social Sciences': [
                        'Department of Economics',
                        'Department of Geography and Resource Development',
                        'Department of Political Science',
                        'Department of Psychology',
                        'Department of Sociology',
                    ]
                }
            },
            'School of Business': {
                'colleges': {
                    'College of Business': [
                        'Department of Accounting',
                        'Department of Finance',
                        'Department of Marketing and Entrepreneurship',
                        'Department of Operations Management and Information Systems',
                        'Department of Organisation and Human Resource Management',
                        'Department of Public Administration and Health Services Management',
                    ]
                }
            },
            'School of Law': {
                'colleges': {
                    'College of Law': [
                        'Department of Law',
                    ]
                }
            },
            'School of Engineering Sciences': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Agricultural Engineering',
                        'Department of Biomedical Engineering',
                        'Department of Computer Engineering',
                        'Department of Food Process Engineering',
                        'Department of Material Science and Engineering',
                        'Department of Petroleum Engineering',
                    ]
                }
            },
            'School of Agriculture': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Agricultural Economics and Agribusiness',
                        'Department of Agricultural Extension',
                        'Department of Animal Science',
                        'Department of Crop Science',
                        'Department of Soil Science',
                    ]
                }
            },
            'School of Biological Sciences': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Animal Biology and Conservation Science',
                        'Department of Biochemistry, Cell and Molecular Biology',
                        'Department of Botany',
                        'Department of Ecology and Environmental Biology',
                        'Department of Marine and Fisheries Sciences',
                        'Department of Microbiology',
                        'Department of Nutrition and Food Science',
                    ]
                }
            },
            'School of Physical and Mathematical Sciences': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Chemistry',
                        'Department of Computer Science',
                        'Department of Earth Science',
                        'Department of Mathematics',
                        'Department of Physics',
                        'Department of Statistics',
                    ]
                }
            },
            'School of Medicine and Health Sciences': {
                'colleges': {
                    'College of Health Sciences': [
                        'Department of Anaesthesia and Intensive Care',
                        'Department of Anatomy',
                        'Department of Behavioural Sciences',
                        'Department of Biochemistry',
                        'Department of Child Health',
                        'Department of Community Health',
                        'Department of Eye, Ear, Nose and Throat',
                        'Department of Family Medicine',
                        'Department of Haematology',
                        'Department of Internal Medicine',
                        'Department of Medical Biochemistry',
                        'Department of Medical Microbiology',
                        'Department of Obstetrics and Gynaecology',
                        'Department of Pathology',
                        'Department of Pharmacology',
                        'Department of Physiology',
                        'Department of Psychiatry',
                        'Department of Radiology',
                        'Department of Surgery',
                    ]
                }
            },
            'School of Pharmacy': {
                'colleges': {
                    'College of Health Sciences': [
                        'Department of Pharmaceutical Chemistry',
                        'Department of Pharmaceutics and Microbiology',
                        'Department of Pharmacognosy and Herbal Medicine',
                        'Department of Pharmacology',
                    ]
                }
            },
            'School of Nursing': {
                'colleges': {
                    'College of Health Sciences': [
                        'Department of Adult Health',
                        'Department of Community Health Nursing',
                        'Department of Maternal and Child Health',
                        'Department of Mental Health Nursing',
                        'Department of Nursing Administration and Education',
                    ]
                }
            },
            'School of Allied Health Sciences': {
                'colleges': {
                    'College of Health Sciences': [
                        'Department of Audiology, Speech and Language',
                        'Department of Dietetics',
                        'Department of Medical Laboratory Science',
                        'Department of Occupational Therapy',
                        'Department of Physiotherapy',
                        'Department of Radiography',
                        'Department of Sports and Exercise Science',
                    ]
                }
            },
            'School of Veterinary Medicine': {
                'colleges': {
                    'College of Basic and Applied Sciences': [
                        'Department of Animal Science',
                        'Department of Pathology',
                        'Department of Physiology',
                        'Department of Veterinary Clinical Studies',
                        'Department of Veterinary Pathology, Microbiology and Parasitology',
                    ]
                }
            },
        }

        school_names = list(data.keys())
        college_names = []
        dept_names = []
        for sname, sdata in data.items():
            for cname, depts in sdata['colleges'].items():
                college_names.append(cname)
                dept_names.extend(depts)

        self.stdout.write(f'Will target {len(dept_names)} departments, {len(college_names)} colleges, {len(school_names)} schools for removal.')

        if dry_run:
            self.stdout.write('DRY RUN: No changes will be made. The following objects would be deleted:')
            for name in dept_names:
                self.stdout.write(f'  Department: {name}')
            for name in college_names:
                self.stdout.write(f'  College: {name}')
            for name in school_names:
                self.stdout.write(f'  School: {name}')
            # Show groups and orphaned permissions that would be deleted
            group_names = set(dept_names + college_names + school_names)
            self.stdout.write('\nDRY RUN: Matching Groups that would be deleted:')
            for name in sorted(group_names):
                self.stdout.write(f'  Group: {name}')

            # Orphaned permissions (no groups and no users)
            orphan_perms = Permission.objects.annotate(gcount=Count('group'), ucount=Count('user')).filter(gcount=0, ucount=0)
            if orphan_perms.exists():
                self.stdout.write('\nDRY RUN: Orphaned Permissions that would be deleted:')
                for p in orphan_perms:
                    self.stdout.write(f'  Permission: {p.content_type.app_label}.{p.codename} ({p.name})')
            else:
                self.stdout.write('\nDRY RUN: No orphaned Permissions found for deletion.')
            return

        # Perform deletions in order to respect FK constraints: Departments -> Colleges -> Schools
        with transaction.atomic():
            depts_qs = Department.objects.filter(name__in=dept_names)
            dcount = depts_qs.count()
            depts_qs.delete()

            colleges_qs = College.objects.filter(name__in=college_names)
            ccount = colleges_qs.count()
            colleges_qs.delete()

            schools_qs = School.objects.filter(name__in=school_names)
            scount = schools_qs.count()
            schools_qs.delete()
            # Also delete any auth Groups that were created for these units
            group_names = set(dept_names + college_names + school_names)
            groups_qs = Group.objects.filter(name__in=group_names)
            gcount = groups_qs.count()

            # Remove group memberships from users to clean M2M entries (safer explicit cleanup)
            User = get_user_model()
            affected_users_qs = User.objects.filter(groups__in=groups_qs).distinct()
            affected_user_count = affected_users_qs.count()
            for group in groups_qs:
                # clear memberships for this group
                group.user_set.clear()

            # Delete groups
            groups_qs.delete()

            # Delete orphaned permissions (permissions not assigned to any group or user)
            orphan_perms_qs = Permission.objects.annotate(gcount=Count('group'), ucount=Count('user')).filter(gcount=0, ucount=0)
            opcount = orphan_perms_qs.count()
            orphan_perms_qs.delete()

        self.stdout.write(self.style.SUCCESS(
            f'Deleted {dcount} departments, {ccount} colleges, {scount} schools, {gcount} groups; cleaned {affected_user_count} user-group memberships; deleted {opcount} orphaned permissions.'
        ))
