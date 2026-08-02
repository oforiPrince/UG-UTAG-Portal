import logging
import os
import secrets
import random
import string
from accounts.models import User, School, College, Department
from accounts.signals import send_email_with_retry
from utag_ug_archiver.utils.constants import executive_members_position_order, executive_committee_members_position_order
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth.hashers import make_password
import pandas as pd
from django.contrib.auth.models import Group
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
# Configure the logger
logger = logging.getLogger(__name__)

def generate_random_password():
    # Generate a random password of 12 characters
    return secrets.token_urlsafe(12)

def ensure_staff_id(user):
    """Ensure user has a staff_id. Generate one if missing."""
    if not user.staff_id:
        existing_ids = set(
            User.objects.exclude(staff_id__isnull=True)
            .exclude(staff_id__exact='')
            .values_list('staff_id', flat=True)
        )
        
        def generate_id():
            return ''.join(random.choices(string.digits, k=6))
        
        staff_id = generate_id()
        while staff_id in existing_ids:
            staff_id = generate_id()
        
        user.staff_id = staff_id
        user.save(update_fields=['staff_id'])
    
    return user.staff_id


def _normalize_value(value):
    """Trim whitespace and turn blank/NaN-like values into None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        # if value is not a pandas-aware type, ignore
        pass

    text = str(value).strip()
    return text if text else None

# Create a custom sorting function based on the order
def executive_members_custom_order(executive):
    return executive_members_position_order.index(executive.executive_position)

def executive_committee_members_custom_order(executive):
    return executive_committee_members_position_order.index(executive.executive_position)


def send_credentials_email(user, raw_password):
        """Send account credentials to a user via email.

        This keeps Celery task imports satisfied and reuses the existing
        retry-aware email helper. If email sending fails, the error is logged.
        """
        try:
            email_subject = 'Account Created'
            from_email = settings.EMAIL_HOST_USER
            email_body = render_to_string('emails/account_credentials.html', {
                'other_name': getattr(user, 'other_name', ''),
                'surname': getattr(user, 'surname', ''),
                'email': user.email,
                'password': raw_password
            })
            email = EmailMessage(
                email_subject,
                email_body,
                from_email,
                [user.email]
            )
            email.content_subtype = "html"
            send_email_with_retry(email)
            logger.info('Credentials email queued for %s', user.email)
        except Exception as e:
            logger.error(f'Error sending credentials email to {user.email}: {e}')
            
def send_reset_password_email(user, reset_url):
        try:
            email_subject = 'Password Reset Request'
            from_email = settings.EMAIL_HOST_USER
            email_body = render_to_string('emails/password_reset_email.html', {
                'full_name': user.get_full_name,
                'reset_url': reset_url
            })
            email = EmailMessage(
                email_subject,
                email_body,
                from_email,
                [user.email]
            )
            email.content_subtype = "html"
            send_email_with_retry(email)
        except Exception as e:
            logger.error(f'Error sending email to {user.email}: {e}')

def process_bulk_admins(request, file):
    file_extension = os.path.splitext(file.name)[1].lower()

    if file_extension != '.csv':
        messages.error(request, 'Invalid file format. Only CSV (.csv) files are allowed.')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    try:
        df = pd.read_csv(file)  # Read CSV file
    except pd.errors.ParserError:
        messages.error(request, 'Invalid CSV file. Please ensure it is properly formatted.')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    # Check for NaN values and fill them or raise an error
    if df.isnull().values.any():
        messages.error(request, 'The file contains missing values. Please fill all the required fields.')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    rename_columns = {
        "Title": "title",
        "First Name": "first_name",
        "Other Name": "other_name",
        "Last Name": "surname",
        "Gender": "gender",
        "Email": "email"
    }
    
    # Handle Staff ID if present in CSV
    if "Staff ID" in df.columns or "StaffId" in df.columns or "staff_id" in df.columns:
        staff_id_col = "Staff ID" if "Staff ID" in df.columns else ("StaffId" if "StaffId" in df.columns else "staff_id")
        rename_columns[staff_id_col] = "staff_id"

    df.rename(columns=rename_columns, inplace=True)

    try:
        for admin in df.itertuples(index=False):
            # Get staff_id from CSV if available, otherwise None
            csv_staff_id = getattr(admin, 'staff_id', None) if hasattr(admin, 'staff_id') else None
            
            # Validate staff_id uniqueness if provided
            if csv_staff_id:
                if User.objects.filter(staff_id=csv_staff_id).exclude(email=admin.email).exists():
                    logger.warning(f"Staff ID {csv_staff_id} already exists for another user. Skipping {admin.email}")
                    continue
            
            # Create or update the user
            user, created = User.objects.update_or_create(
                email=admin.email,
                defaults={
                    'title': admin.title,
                    'other_name': admin.other_name,
                    'surname': getattr(admin, 'surname', admin.last_name if hasattr(admin, 'last_name') else ''),
                    'gender': admin.gender,
                    'staff_id': csv_staff_id if csv_staff_id else None,
                    'created_from_dashboard': True,
                    'created_by': request.user,
                    'is_bulk_creation': True,
                    'must_change_password': True,
                }
            )
            
            # Ensure staff_id exists and use it as temporary password
            staff_id = ensure_staff_id(user)
            user.password = make_password(staff_id)
            user.save(update_fields=['password'])
            
            # Add the user to the Admin group
            user.groups.add(Group.objects.get(name='Admin'))

        messages.success(request, f'{len(df)} admin(s) processed successfully!')
    except Exception as e:
        messages.error(request, f'Error during import: {e}')
    
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

def process_bulk_members(request, file):
    file_extension = os.path.splitext(file.name)[1].lower()

    allowed_exts = {'.csv', '.xlsx', '.xls'}
    if file_extension not in allowed_exts:
        messages.error(request, 'Invalid file format. Please upload a CSV (.csv) or Excel file (.xlsx, .xls).')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    try:
        if file_extension == '.csv':
            df = pd.read_csv(file)
        else:
            # For .xlsx/.xls (requires openpyxl for xlsx; xlrd may be needed for older .xls)
            df = pd.read_excel(file)
    except pd.errors.ParserError:
        messages.error(request, 'Invalid CSV file. Please ensure it is properly formatted.')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    except Exception as e:
        # Catch common Excel-engine issues (missing dependency, corrupt workbook, etc.)
        messages.error(request, f'Unable to read the uploaded file. Please upload a valid CSV/Excel file. ({e})')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    # Case-insensitive, trimmed header mapping (dedup variants)
    header_map = {
        'title': 'title',
        'first name': 'first_name',
        'other name': 'other_name',
        'other names': 'other_name',
        'last name': 'surname',
        'surname': 'surname',
        'gender': 'gender',
        'email': 'email',
        'email address': 'email',
        'phone number': 'phone_number',
        'rank': 'academic_rank',
        'department': 'department',
        'college': 'college',
        'school': 'school',
        'faculty (school)': 'school',
        'staff id': 'staff_id',
        'staffid': 'staff_id',
        'staff_id': 'staff_id',
    }

    col_renames = {}
    for col in df.columns:
        norm = str(col).strip().lower()
        target = header_map.get(norm)
        if target:
            col_renames[col] = target

    df.rename(columns=col_renames, inplace=True)

    # Relax requireds: take names/email/department; defer title/gender/phone to first login update
    required_fields = ['other_name', 'surname', 'email', 'department']
    missing_required_columns = [col for col in required_fields if col not in df.columns]
    if missing_required_columns:
        messages.error(request, f"Missing required column(s): {', '.join(missing_required_columns)}. Please use the sample template format.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    # Note: Excel/CSV exports often contain blank cells. We enforce required columns,
    # but we won't fail the entire upload if some rows are missing values.
    # We'll skip incomplete rows and report how many were skipped.

    unmatched_departments = set()
    processed = 0
    skipped = 0
    skipped_incomplete = 0
    created_schools = 0
    created_colleges = 0
    created_departments = 0

    # Hot-path caches (avoid repetitive DB hits on large files)
    member_group = Group.objects.get(name='Member')
    school_cache = {}
    college_cache = {}
    department_cache = {}

    # Preload staff_id ownership to avoid N queries (only for non-empty staff_ids in the sheet)
    staff_ids_in_sheet = (
        df.get('staff_id', pd.Series(dtype=object))
        .dropna()
        .astype(str)
        .str.strip()
    )
    staff_ids_in_sheet = [s for s in staff_ids_in_sheet.tolist() if s]
    existing_staff_id_to_email = {}
    if staff_ids_in_sheet:
        existing_staff_id_to_email = dict(
            User.objects
            .filter(staff_id__in=staff_ids_in_sheet)
            .values_list('staff_id', 'email')
        )

    try:
        for member in df.itertuples(index=False):
            # Normalize incoming values (use safe defaults for title/gender if missing)
            title = _normalize_value(getattr(member, 'title', None))
            other_name = _normalize_value(getattr(member, 'other_name', None)) or _normalize_value(getattr(member, 'first_name', None))
            surname = _normalize_value(getattr(member, 'surname', None)) or _normalize_value(getattr(member, 'last_name', None))
            gender = _normalize_value(getattr(member, 'gender', None))
            email = _normalize_value(getattr(member, 'email', None))
            phone_number = _normalize_value(getattr(member, 'phone_number', None))
            dept_name = _normalize_value(getattr(member, 'department', None))
            college_name = _normalize_value(getattr(member, 'college', None))
            school_name = _normalize_value(getattr(member, 'school', None))
            csv_staff_id = _normalize_value(getattr(member, 'staff_id', None)) if hasattr(member, 'staff_id') else None
            rank = _normalize_value(getattr(member, 'academic_rank', None))

            # Minimum per-row requirements for account creation.
            # We'll force members to complete full profiles after first login.
            if not email or not dept_name or not surname or not other_name:
                skipped_incomplete += 1
                continue

            # Allow missing title/gender; users will be prompted to complete on first login
            if not title:
                title = ''
            if not gender:
                gender = ''

            # Validate staff_id uniqueness if provided
            if csv_staff_id:
                owner_email = existing_staff_id_to_email.get(csv_staff_id)
                if owner_email and owner_email != email:
                    logger.warning(f"Staff ID {csv_staff_id} already exists for another user. Skipping {email}")
                    skipped += 1
                    continue

            # Resolve or create school
            school_obj = None
            if school_name:
                school_key = school_name.casefold()
                school_obj = school_cache.get(school_key)
                if school_obj is None:
                    school_obj = School.objects.filter(name__iexact=school_name).first()
                    if not school_obj:
                        school_obj = School.objects.create(name=school_name)
                        created_schools += 1
                    school_cache[school_key] = school_obj

            # Resolve or create college
            college_obj = None
            if college_name:
                college_key = (college_name.casefold(), getattr(school_obj, 'id', None))
                college_obj = college_cache.get(college_key)
                if college_obj is None:
                    college_qs = College.objects.filter(name__iexact=college_name)
                    if school_obj:
                        college_qs = college_qs.filter(school=school_obj)
                    college_obj = college_qs.first()
                    if not college_obj:
                        college_obj = College.objects.create(name=college_name, school=school_obj)
                        created_colleges += 1
                    college_cache[college_key] = college_obj

            # Resolve or create department (with optional college linkage)
            department_obj = None
            if dept_name:
                dept_key = (dept_name.casefold(), getattr(college_obj, 'id', None))
                department_obj = department_cache.get(dept_key)
                if department_obj is None:
                    dept_qs = Department.objects.filter(name__iexact=dept_name)
                    if college_obj:
                        dept_qs = dept_qs.filter(college=college_obj)
                    department_obj = dept_qs.first()
                    if not department_obj:
                        department_obj = Department.objects.create(name=dept_name, college=college_obj)
                        created_departments += 1
                    department_cache[dept_key] = department_obj

            if not department_obj:
                unmatched_departments.add(dept_name or 'Unknown department')
                skipped += 1
                continue

            # Create or update the user
            user, created = User.objects.update_or_create(
                email=email,
                defaults={
                    'title': title,
                    'other_name': other_name,
                    'surname': surname or '',
                    'gender': gender,
                    'phone_number': phone_number,
                    'department': department_obj,
                    'college': college_obj,
                    'school': school_obj,
                    'academic_rank': rank,
                    'staff_id': csv_staff_id if csv_staff_id else None,
                    'created_from_dashboard': True,
                    'created_by': request.user,
                    'is_bulk_creation': True,
                    'must_change_password': True,
                }
            )
            
            # Ensure staff_id exists and use it as temporary password
            staff_id = ensure_staff_id(user)
            user.password = make_password(staff_id)
            user.save(update_fields=['password'])
            
            # Add the user to the Member group
            user.groups.add(member_group)
            processed += 1

        if processed:
            msg = f'{processed} member(s) processed successfully!'
            created_bits = []
            if created_schools:
                created_bits.append(f'{created_schools} school(s) created')
            if created_colleges:
                created_bits.append(f'{created_colleges} college(s) created')
            if created_departments:
                created_bits.append(f'{created_departments} department(s) created')
            if created_bits:
                msg += ' ' + '; '.join(created_bits) + '.'
            messages.success(request, msg)

        if skipped:
            messages.warning(request, f'{skipped} row(s) skipped because the Department name did not match existing records: {", ".join(sorted(unmatched_departments))}')

        if skipped_incomplete:
            messages.warning(
                request,
                f'{skipped_incomplete} row(s) skipped because required values were missing (Other Names, Last Name, Email Address, Department).'
            )
    except Exception as e:
        messages.error(request, f'Error during import: {e}')
    
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
