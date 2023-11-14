import os
from utag_ug_archiver.utils.constants import officers_position_order, committee_members_position_order
from django.http import HttpResponseRedirect
from django.contrib import messages
from tablib import Dataset
from accounts.serializers import UserResource
import pandas as pd
# Create a custom sorting function based on the order
def officers_custom_order(executive):
    return officers_position_order.index(executive.position.name)

def members_custom_order(executive):
    return committee_members_position_order.index(executive.position.name)

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
        # Send email to admin with password
        
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
        # Send email to admin with password
        
        messages.success(request, f'{num_success} member(s) uploaded successfully!')
    else:
        messages.error(request, 'Error Importing Member Data')

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
