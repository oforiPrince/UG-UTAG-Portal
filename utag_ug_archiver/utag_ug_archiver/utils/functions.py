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

    if file_extension == '.xlsx':
        try:
            df = pd.read_excel(file)  # Read as Excel file
        except pd.errors.ParserError:
            messages.error(request, 'Invalid file format. Only Excel (.xlsx) or CSV (.csv) files are allowed.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    elif file_extension == '.csv':
        try:
            df = pd.read_csv(file)  # Read as CSV file
        except pd.errors.ParserError:
            messages.error(request, 'Invalid file format. Only Excel (.xlsx) or CSV (.csv) files are allowed.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    else:
        messages.error(request, 'Invalid file format. Only Excel (.xlsx) or CSV (.csv) files are allowed.')
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
    df['is_admin'] = True

    member_resource = UserResource()
    dataset = Dataset().load(df.to_csv(index=False))
    result = member_resource.import_data(dataset, dry_run=True, raise_errors=True)

    if not result.has_errors():
        result = member_resource.import_data(dataset, dry_run=False)
        num_success = len(result.rows)
        
        # Send email to each admin with password
        for admin in df.itertuples():
            email_subject = 'Account Created'
            from_email = settings.EMAIL_HOST_USER
            to = admin.email
            password = generate_random_password()
            email_body = render_to_string('emails/account_credentials.html', {'first_name': admin.first_name,'last_name': admin.last_name,'email':admin.email, 'password': password})
            email = EmailMessage(
                email_subject,
                email_body,
                from_email,
                [to]
            )
            email.content_subtype = "html"
            email.send()

            # update the password in the database
            user = User.objects.get(email=admin.email)
            user.password = make_password(password)
            user.save()

        messages.success(request, f'{num_success} admin(s) uploaded successfully!')
    else:
        messages.error(request, 'Error Importing Admin Data')

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def process_bulk_members(request,file):
    file_extension = os.path.splitext(file.name)[1].lower()

    if file_extension == '.xlsx':
        try:
            df = pd.read_excel(file)  # Read as Excel file
        except pd.errors.ParserError:
            messages.error(request, 'Invalid file format. Only Excel (.xlsx) or CSV (.csv) files are allowed.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    elif file_extension == '.csv':
        try:
            df = pd.read_csv(file)  # Read as CSV file
        except pd.errors.ParserError:
            messages.error(request, 'Invalid file format. Only Excel (.xlsx) or CSV (.csv) files are allowed.')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    else:
        messages.error(request, 'Invalid file format. Only Excel (.xlsx) or CSV (.csv) files are allowed.')
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
    df['is_member'] = True
    member_resource = UserResource()
    dataset = Dataset().load(df.to_csv(index=False))
    result = member_resource.import_data(dataset, dry_run=True, raise_errors=True)
    print(result)
    if not result.has_errors():
        result = member_resource.import_data(dataset, dry_run=False)
        num_success = len(result.rows)
        
        # Send email to each admin with password
        for member in df.itertuples():
            email_subject = 'Account Created'
            from_email = settings.EMAIL_HOST_USER
            to = member.email
            password = generate_random_password()
            email_body = render_to_string('emails/account_credentials.html', {'first_name': member.first_name,'last_name': member.last_name,'email':member.email, 'password': password})
            email = EmailMessage(
                email_subject,
                email_body,
                from_email,
                [to]
            )
            email.content_subtype = "html"
            email.send()

            # update the password in the database
            user = User.objects.get(email=member.email)
            user.password = make_password(password)
            user.save()

        messages.success(request, f'{num_success} member(s) uploaded successfully!')
    else:
        messages.error(request, 'Error Importing Member Data')

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
