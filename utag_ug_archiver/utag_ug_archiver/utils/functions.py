import os
import secrets
from accounts.models import User
from utag_ug_archiver.utils.constants import officers_position_order, committee_members_position_order
from django.http import HttpResponseRedirect
from django.contrib import messages
import pandas as pd
from django.contrib.auth.models import Group
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

def generate_random_password():
    # Generate a random password of 12 characters
    return secrets.token_urlsafe(12)

# Create a custom sorting function based on the order
def officers_custom_order(executive):
    return officers_position_order.index(executive.position.name)

def members_custom_order(executive):
    return committee_members_position_order.index(executive.position.name)

def send_credentials_email(user, password):
    subject = 'Your Account Information'
    message = render_to_string('accounts/emails/credentials_email.html', {
        'user': user,
        'password': password,
    })
    email = EmailMessage(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email]
    )

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
        "Last Name": "last_name",
        "Gender": "gender",
        "Email": "email"
    }

    df.rename(columns=rename_columns, inplace=True)

    try:
        for admin in df.itertuples(index=False):
            # Check if the admin already exists
            user, created = User.objects.update_or_create(
                email=admin.email,
                defaults={
                    'title': admin.title,
                    'first_name': admin.first_name,
                    'other_name': admin.other_name,
                    'last_name': admin.last_name,
                    'gender': admin.gender,
                    'created_from_dashboard': True
                }
            )
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

    # Check for NaN values and fill them or raise an error
    if df.isnull().values.any():
        messages.error(request, 'The file contains missing values. Please fill all the required fields.')
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    
    rename_columns = {
        "Title": "title",
        "First Name": "first_name",
        "Other Name": "other_name",
        "Last Name": "last_name",
        "Gender": "gender",
        "Email": "email",
        "Phone Number": "phone_number",
        "Department": "department"
    }

    df.rename(columns=rename_columns, inplace=True)

    try:
        for member in df.itertuples(index=False):
            # Check if the user already exists
            user, created = User.objects.update_or_create(
                email=member.email,
                defaults={
                    'title': member.title,
                    'first_name': member.first_name,
                    'other_name': member.other_name,
                    'last_name': member.last_name,
                    'gender': member.gender,
                    'phone_number': member.phone_number,
                    'department': member.department,
                    'created_from_dashboard': True
                }
            )
            # Add the user to the Member group
            user.groups.add(Group.objects.get(name='Member'))

        messages.success(request, f'{len(df)} member(s) processed successfully!')
    except Exception as e:
        messages.error(request, f'Error during import: {e}')
    
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))