import logging
import os

import pandas as pd
from celery import shared_task
from utag_ug_archiver.utils.functions import _normalize_value, ensure_staff_id
from typing import Dict, Tuple, Optional


logger = logging.getLogger(__name__)


def _read_tabular_file(file_path: str) -> pd.DataFrame:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.csv':
        return pd.read_csv(file_path)
    if ext in {'.xlsx', '.xls'}:
        return pd.read_excel(file_path)
    raise ValueError(f'Unsupported file extension: {ext}')


@shared_task(bind=True)
def import_members_from_upload(self, relative_media_path: str, uploaded_by_user_id: Optional[int] = None) -> dict:
    """Background import for large member uploads.

    Contract:
    - Input: relative path under MEDIA_ROOT where the uploaded file was saved.
    - Output: dict summary {processed, skipped_incomplete, skipped_staff_id, skipped_department, created_*}
    - Error mode: raises exception (Celery will record failure)
    """

    # Defer Django imports so this module can be imported without Django app registry initialization.
    from django.conf import settings
    from django.contrib.auth.hashers import make_password
    from django.contrib.auth.models import Group
    from django.db import IntegrityError
    from django.db import transaction

    from accounts.models import College, Department, School, User

    file_path = os.path.join(settings.MEDIA_ROOT, relative_media_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f'Upload file not found: {file_path}')

    df = _read_tabular_file(file_path)

    # Case-insensitive, trimmed header mapping
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

    required_fields = ['other_name', 'surname', 'email', 'department']
    missing_required_columns = [col for col in required_fields if col not in df.columns]
    if missing_required_columns:
        raise ValueError(f"Missing required column(s): {', '.join(missing_required_columns)}")
    member_group = Group.objects.get(name='Member')
    school_cache: Dict[str, School] = {}
    college_cache: Dict[Tuple[str, Optional[int]], College] = {}
    department_cache: Dict[Tuple[str, Optional[int]], Department] = {}

    staff_ids_in_sheet = (
        df.get('staff_id', pd.Series(dtype=object))
        .dropna()
        .astype(str)
        .str.strip()
    )
    staff_ids_in_sheet = [s for s in staff_ids_in_sheet.tolist() if s]
    existing_staff_id_to_email: dict[str, str] = {}
    if staff_ids_in_sheet:
        existing_staff_id_to_email = dict(
            User.objects.filter(staff_id__in=staff_ids_in_sheet).values_list('staff_id', 'email')
        )

    processed = 0
    skipped_incomplete = 0
    skipped_staff_id = 0
    skipped_department = 0
    created_schools = 0
    created_colleges = 0
    created_departments = 0

    uploaded_by = None
    if uploaded_by_user_id:
        uploaded_by = User.objects.filter(pk=uploaded_by_user_id).first()

    # Stage rows (pure Python) before we touch the DB heavily.
    staged: list[dict] = []
    emails: list[str] = []

    for idx, member in enumerate(df.itertuples(index=False), start=1):
        title = _normalize_value(getattr(member, 'title', None)) or ''
        other_name = _normalize_value(getattr(member, 'other_name', None)) or _normalize_value(getattr(member, 'first_name', None))
        surname = _normalize_value(getattr(member, 'surname', None)) or _normalize_value(getattr(member, 'last_name', None))
        gender = _normalize_value(getattr(member, 'gender', None)) or ''
        email = _normalize_value(getattr(member, 'email', None))
        phone_number = _normalize_value(getattr(member, 'phone_number', None))
        dept_name = _normalize_value(getattr(member, 'department', None))
        college_name = _normalize_value(getattr(member, 'college', None))
        school_name = _normalize_value(getattr(member, 'school', None))
        csv_staff_id = _normalize_value(getattr(member, 'staff_id', None)) if hasattr(member, 'staff_id') else None
        rank = _normalize_value(getattr(member, 'academic_rank', None))

        if not email or not dept_name or not surname or not other_name:
            skipped_incomplete += 1
            if idx <= 10 or idx % 100 == 0:
                logger.warning(
                    f"Row {idx} skipped (incomplete): email={email}, surname={surname}, "
                    f"other_name={other_name}, dept={dept_name}"
                )
            continue

        if csv_staff_id:
            owner_email = existing_staff_id_to_email.get(csv_staff_id)
            if owner_email and owner_email != email:
                skipped_staff_id += 1
                if idx <= 10 or idx % 100 == 0:
                    logger.warning(
                        f"Row {idx} skipped (staff_id conflict): staff_id={csv_staff_id}, "
                        f"requested_email={email}, existing_email={owner_email}"
                    )
                continue

        # Resolve org units with cache (may create as needed)
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

        college_obj = None
        if college_name:
            college_key = (college_name.casefold(), getattr(school_obj, 'id', None))
            college_obj = college_cache.get(college_key)
            if college_obj is None:
                qs = College.objects.filter(name__iexact=college_name)
                if school_obj:
                    qs = qs.filter(school=school_obj)
                college_obj = qs.first()
                if not college_obj:
                    college_obj = College.objects.create(name=college_name, school=school_obj)
                    created_colleges += 1
                college_cache[college_key] = college_obj

        department_obj = None
        if dept_name:
            dept_key = (dept_name.casefold(), getattr(college_obj, 'id', None))
            department_obj = department_cache.get(dept_key)
            if department_obj is None:
                qs = Department.objects.filter(name__iexact=dept_name)
                if college_obj:
                    qs = qs.filter(college=college_obj)
                department_obj = qs.first()
                if not department_obj:
                    department_obj = Department.objects.create(name=dept_name, college=college_obj)
                    created_departments += 1
                department_cache[dept_key] = department_obj

        if not department_obj:
            skipped_department += 1
            if idx <= 10 or idx % 100 == 0:
                logger.warning(
                    f"Row {idx} skipped (department not found): dept_name={dept_name}, "
                    f"college={college_name}, school={school_name}"
                )
            continue

        staged.append({
            'email': email,
            'title': title,
            'other_name': other_name,
            'surname': surname,
            'gender': gender,
            'phone_number': phone_number,
            'department_id': getattr(department_obj, 'id', None),
            'college_id': getattr(college_obj, 'id', None),
            'school_id': getattr(school_obj, 'id', None),
            'academic_rank': rank,
            'staff_id': csv_staff_id,
        })
        emails.append(email)

    # One query: fetch existing users by email
    existing_by_email = User.objects.in_bulk(emails, field_name='email') if emails else {}

    to_create: list[User] = []
    to_update: list[User] = []

    for row in staged:
        existing = existing_by_email.get(row['email'])
        if existing is None:
            to_create.append(
                User(
                    email=row['email'],
                    title=row['title'],
                    other_name=row['other_name'],
                    surname=row['surname'] or '',
                    gender=row['gender'],
                    phone_number=row['phone_number'],
                    department_id=row['department_id'],
                    college_id=row['college_id'],
                    school_id=row['school_id'],
                    academic_rank=row['academic_rank'],
                    staff_id=row['staff_id'] if row['staff_id'] else None,
                    created_from_dashboard=True,
                    created_by=uploaded_by,
                    is_bulk_creation=True,
                    must_change_password=True,
                )
            )
        else:
            existing.title = row['title']
            existing.other_name = row['other_name']
            existing.surname = row['surname'] or ''
            existing.gender = row['gender']
            existing.phone_number = row['phone_number']
            existing.department_id = row['department_id']
            existing.college_id = row['college_id']
            existing.school_id = row['school_id']
            existing.academic_rank = row['academic_rank']
            if row['staff_id']:
                existing.staff_id = row['staff_id']
            existing.created_from_dashboard = True
            existing.is_bulk_creation = True
            existing.must_change_password = True
            # Keep created_by for existing users unchanged
            to_update.append(existing)

    with transaction.atomic():
        created_count = len(to_create)
        updated_count = len(to_update)
        logger.info(f"About to create {created_count} new users and update {updated_count} existing users")
        
        if to_create:
            # ignore_conflicts protects against concurrent uploads creating same email
            User.objects.bulk_create(to_create, ignore_conflicts=True)
            logger.info(f"bulk_create completed for {created_count} users")

        if to_update:
            User.objects.bulk_update(
                to_update,
                fields=[
                    'title',
                    'other_name',
                    'surname',
                    'gender',
                    'phone_number',
                    'department_id',
                    'college_id',
                    'school_id',
                    'academic_rank',
                    'staff_id',
                    'created_from_dashboard',
                    'is_bulk_creation',
                    'must_change_password',
                ],
            )
            logger.info(f"bulk_update completed for {updated_count} users")

        # Re-fetch users for password + group membership steps
        all_users_by_email = User.objects.in_bulk(emails, field_name='email') if emails else {}

        # Passwords + ensure_staff_id
        to_update_password: list[User] = []
        for u in all_users_by_email.values():
            staff_id = ensure_staff_id(u)
            u.password = make_password(staff_id)
            to_update_password.append(u)

        if to_update_password:
            User.objects.bulk_update(to_update_password, fields=['password'])

        # Group membership in bulk (auth_user_groups through table)
        # Cast PKs to concrete ints to keep static type checkers happy.
        member_group_id = int(member_group.pk)
        through = User.groups.through
        user_ids = [int(u.pk) for u in all_users_by_email.values()]
        existing_links = set(
            through.objects.filter(
                user_id__in=user_ids,
                group_id=member_group_id,
            ).values_list('user_id', flat=True)
        )
        new_links = [
            through(user_id=int(u.pk), group_id=member_group_id)
            for u in all_users_by_email.values()
            if int(u.pk) not in existing_links
        ]
        if new_links:
            try:
                through.objects.bulk_create(new_links, ignore_conflicts=True)
            except IntegrityError:
                # best-effort; ignore duplicates
                pass

    processed = len(emails)

    summary = {
        'processed': processed,
        'new_users': created_count,
        'updated_users': updated_count,
        'skipped_incomplete': skipped_incomplete,
        'skipped_staff_id': skipped_staff_id,
        'skipped_department': skipped_department,
        'created_schools': created_schools,
        'created_colleges': created_colleges,
        'created_departments': created_departments,
        'file': relative_media_path,
    }
    logger.info(
        f'Bulk member import complete: {summary} | '
        f'Total rows in file: {len(df)} | '
        f'Valid rows staged: {len(emails)}'
    )
    return summary
