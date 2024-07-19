import os
import secrets
from accounts.models import User
from utag_ug_archiver.utils.constants import officers_position_order, committee_members_position_order
from django.http import HttpResponseRedirect
from django.contrib import messages
from tablib import Dataset
from accounts.serializers import UserResource
import pandas as pd
from django.contrib.auth.hashers import make_password
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

    # Debugging: Print data types
    print(df.dtypes)

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
                }
            )

            # Add the user to the Admin group (replace with appropriate group name)
            user.groups.add(Group.objects.get(name='Admin'))

            if created:
                # If the admin was created, send email with password
                email_subject = 'Account Created'
                from_email = settings.EMAIL_HOST_USER
                to = admin.email
                password = generate_random_password()
                email_body = render_to_string('emails/account_credentials.html', {
                    'first_name': admin.first_name,
                    'last_name': admin.last_name,
                    'email': admin.email,
                    'password': password
                })
                email = EmailMessage(
                    email_subject,
                    email_body,
                    from_email,
                    [to]
                )
                email.content_subtype = "html"
                email.send()

                # Update the password in the database
                user.password = make_password(password)
                user.save()

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

    # Debugging: Print data types
    print(df.dtypes)

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
                }
            )

            # Add the user to the Member group (replace with appropriate group name)
            user.groups.add(Group.objects.get(name='Member'))

            if created:
                # If the user was created, send email with password
                email_subject = 'Account Created'
                from_email = settings.EMAIL_HOST_USER
                to = member.email
                password = generate_random_password()
                email_body = render_to_string('emails/account_credentials.html', {
                    'first_name': member.first_name,
                    'last_name': member.last_name,
                    'email': member.email,
                    'password': password
                })
                email = EmailMessage(
                    email_subject,
                    email_body,
                    from_email,
                    [to]
                )
                email.content_subtype = "html"
                email.send()

                # Update the password in the database
                user.password = make_password(password)
                user.save()

        messages.success(request, f'{len(df)} member(s) processed successfully!')
    except Exception as e:
        messages.error(request, f'Error during import: {e}')
    
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))