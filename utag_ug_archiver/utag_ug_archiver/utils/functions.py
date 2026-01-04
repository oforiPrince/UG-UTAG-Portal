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

    if file_extension != '.csv':
        messages.error(request, 'Invalid file format. Only CSV (.csv) files are allowed.')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    try:
        df = pd.read_csv(file)  # Read CSV file
    except pd.errors.ParserError:
        messages.error(request, 'Invalid CSV file. Please ensure it is properly formatted.')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    rename_columns = {
        "Title": "title",
        "First Name": "first_name",
        "Other Name": "other_name",
        "Last Name": "surname",
        "Gender": "gender",
        "Email": "email",
        "Phone Number": "phone_number",
        "Department": "department",
        "College": "college",
        "School": "school",
    }
    
    # Handle Staff ID if present in CSV
    if "Staff ID" in df.columns or "StaffId" in df.columns or "staff_id" in df.columns:
        staff_id_col = "Staff ID" if "Staff ID" in df.columns else ("StaffId" if "StaffId" in df.columns else "staff_id")
        rename_columns[staff_id_col] = "staff_id"

    df.rename(columns=rename_columns, inplace=True)

    required_fields = ['title', 'other_name', 'surname', 'gender', 'email', 'department']
    missing_required_columns = [col for col in required_fields if col not in df.columns]
    if missing_required_columns:
        messages.error(request, f"Missing required column(s): {', '.join(missing_required_columns)}. Please use the sample CSV format.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    if df[required_fields].isnull().values.any():
        messages.error(request, 'The file contains missing values in required columns (Title, Other Name, Last Name, Gender, Email, Department). Please fill them and try again.')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    unmatched_departments = set()
    processed = 0
    skipped = 0

    try:
        for member in df.itertuples(index=False):
            # Normalize incoming values
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

            # Validate staff_id uniqueness if provided
            if csv_staff_id and User.objects.filter(staff_id=csv_staff_id).exclude(email=email).exists():
                logger.warning(f"Staff ID {csv_staff_id} already exists for another user. Skipping {email}")
                skipped += 1
                continue

            # Resolve department (with optional college/school hints)
            department_obj = None
            if dept_name:
                dept_qs = Department.objects.filter(name__iexact=dept_name)
                if college_name:
                    dept_qs = dept_qs.filter(college__name__iexact=college_name)
                if school_name:
                    dept_qs = dept_qs.filter(college__school__name__iexact=school_name)

                department_obj = dept_qs.first()

            if not department_obj:
                unmatched_departments.add(dept_name or 'Unknown department')
                skipped += 1
                continue

            college_obj = department_obj.college
            school_obj = college_obj.school if college_obj else None

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
            user.groups.add(Group.objects.get(name='Member'))
            processed += 1

        if processed:
            messages.success(request, f'{processed} member(s) processed successfully!')
        if skipped:
            messages.warning(request, f'{skipped} row(s) skipped because the Department name did not match existing records: {", ".join(sorted(unmatched_departments))}')
    except Exception as e:
        messages.error(request, f'Error during import: {e}')
    
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
