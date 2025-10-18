from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.db import IntegrityError
from accounts.models import User
from chat.models import ChatThread, ChatGroup, GroupMembership
import json
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from chat.models import MessageAttachment, GroupMessageAttachment
from django.views.decorators.csrf import csrf_exempt


@login_required
@require_http_methods(["GET"])
def get_users_list(request):
    """
    API endpoint to get list of users for direct chat or group creation
    Excludes the current user
    """
    users = User.objects.filter(
        is_active=True
    ).exclude(
        id=request.user.id
    ).values('id', 'other_name', 'surname', 'title', 'profile_pic')
    
    users_list = []
    for user in users:
        users_list.append({
            'id': user['id'],
            'name': f"{user['other_name']} {user['surname']}",
            'title': user['title'] or '',
            'avatar': user['profile_pic'] if user['profile_pic'] else None,
            'initial': user['other_name'][0].upper() if user['other_name'] else '?'
        })
    
    return JsonResponse({'success': True, 'users': users_list})


@login_required
@require_http_methods(["POST"])
def start_direct_chat(request):
    """
    API endpoint to start a direct chat with a user
    Creates thread if doesn't exist, returns URL to chat
    """
    try:
        # Accept JSON body or form-encoded POST
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            user_id = data.get('user_id')
            message = data.get('message')
        else:
            user_id = request.POST.get('user_id') or request.POST.get('recipient_id')
            message = request.POST.get('message')
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'User ID required'}, status=400)
        
        other_user = User.objects.get(id=user_id)
        
        # Check if thread already exists (in either direction)
        thread = ChatThread.objects.filter(
            Q(user_one=request.user, user_two=other_user) |
            Q(user_one=other_user, user_two=request.user)
        ).first()
        
        if not thread:
            # Create new thread
            thread = ChatThread.objects.create(
                user_one=request.user,
                user_two=other_user
            )
        
        return JsonResponse({
            'success': True,
            'url': f'/chat/thread/{thread.id}/',
            'redirect_url': f'/chat/thread/{thread.id}/'
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def create_group_ajax(request):
    """
    API endpoint to create a group chat with multiple members
    Returns URL to new group chat
    """
    try:
        # Accept JSON body or form-encoded POST
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            group_name = data.get('name')
            member_ids = data.get('member_ids', [])
        else:
            group_name = request.POST.get('name')
            # If form-encoded, members may be provided as multiple 'members' fields
            member_ids = request.POST.getlist('members') or request.POST.getlist('member_ids')
        
        if not group_name:
            return JsonResponse({'success': False, 'error': 'Group name required'}, status=400)
        
        if not member_ids:
            return JsonResponse({'success': False, 'error': 'At least one member required'}, status=400)
        
        # Check permissions (only executives and staff can create groups)
        if not ((hasattr(request.user, 'is_executive') and request.user.is_executive) or request.user.is_staff):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        # Normalize group name and member ids
        group_name = group_name.strip()
        try:
            member_ids = list(dict.fromkeys(int(x) for x in member_ids))
        except Exception:
            # member_ids might already be integers or malformed; try best-effort
            cleaned = []
            for mid in member_ids:
                try:
                    cleaned.append(int(mid))
                except Exception:
                    continue
            member_ids = list(dict.fromkeys(cleaned))

        # If a group with the same name exists for this creator, return it instead of creating a duplicate
        existing = ChatGroup.objects.filter(name=group_name, created_by=request.user).first()
        if existing:
            return JsonResponse({
                'success': True,
                'url': f'/chat/group/{existing.id}/',
                'redirect_url': f'/chat/group/{existing.id}/',
                'message': 'Group already exists'
            })

        # Create the group
        try:
            group = ChatGroup.objects.create(
                name=group_name,
                created_by=request.user
            )
        except IntegrityError as e:
            # Another request may have created the group concurrently; try to fetch and return it
            existing = ChatGroup.objects.filter(name=group_name, created_by=request.user).first()
            if existing:
                return JsonResponse({
                    'success': True,
                    'url': f'/chat/group/{existing.id}/',
                    'redirect_url': f'/chat/group/{existing.id}/',
                    'message': 'Group already exists'
                })
            return JsonResponse({'success': False, 'error': 'Could not create group', 'details': str(e)}, status=500)
        
        # Add creator as a member (record who added them)
        GroupMembership.objects.create(
            group=group,
            user=request.user,
            added_by=request.user
        )
        
        # Add selected members
        for member_id in member_ids:
            try:
                user = User.objects.get(id=member_id)
                if user.id != request.user.id:  # Don't add creator twice
                    GroupMembership.objects.create(
                        group=group,
                        user=user,
                        added_by=request.user
                    )
            except User.DoesNotExist:
                continue
        
        return JsonResponse({
            'success': True,
            'url': f'/chat/group/{group.id}/',
            'redirect_url': f'/chat/group/{group.id}/',
            'message': f'Group created with {len(member_ids)} members'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



@login_required
@require_http_methods(["POST"])
def mark_thread_read(request, thread_id):
    """
    Mark all unread messages in a thread as read by the requesting user.
    """
    try:
        thread = ChatThread.objects.get(pk=thread_id)
        # ensure participant
        if not thread.is_participant(request.user):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        thread.mark_messages_as_read(request.user)
        return JsonResponse({'success': True})
    except ChatThread.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Thread not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def mark_group_read(request, group_id):
    """
    Mark group messages as read for the requesting user (adds user to read_by for unread group messages).
    """
    try:
        group = ChatGroup.objects.get(pk=group_id)
        if not group.members.filter(id=request.user.id).exists():
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        unread = group.messages.exclude(sender=request.user).exclude(read_by=request.user)
        for msg in unread:
            msg.read_by.add(request.user)

        return JsonResponse({'success': True})
    except ChatGroup.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Group not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def download_message_attachment(request, attachment_id):
    """Download and decrypt a direct message attachment, ensure requester is a thread participant."""
    att = get_object_or_404(MessageAttachment, pk=attachment_id)
    thread = att.message.thread
    if not thread.is_participant(request.user):
        raise Http404('Not found')
    data = att.get_content()
    response = HttpResponse(data, content_type=att.content_type or 'application/octet-stream')
    response['Content-Length'] = str(att.size)
    # Allow inline viewing for images and PDFs; force download for other types
    if att.content_type:
        if att.content_type.startswith('image/') or att.content_type == 'application/pdf':
            response['Content-Disposition'] = f'inline; filename="{att.filename}"'
        else:
            response['Content-Disposition'] = f'attachment; filename="{att.filename}"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{att.filename}"'
    return response


@login_required
@require_http_methods(["GET"])
def download_message_attachment_thumbnail(request, attachment_id):
    att = get_object_or_404(MessageAttachment, pk=attachment_id)
    thread = att.message.thread
    if not thread.is_participant(request.user):
        raise Http404('Not found')
    data = att.get_thumbnail_content()
    if data is None:
        raise Http404('Thumbnail not available')
    response = HttpResponse(data, content_type='image/png')
    response['Content-Length'] = str(len(data))
    response['Content-Disposition'] = f'inline; filename="{att.filename}.png"'
    return response


@login_required
@require_http_methods(["GET"])
def download_group_message_attachment(request, attachment_id):
    att = get_object_or_404(GroupMessageAttachment, pk=attachment_id)
    group = att.message.group
    if not group.is_member(request.user):
        raise Http404('Not found')
    data = att.get_content()
    response = HttpResponse(data, content_type=att.content_type or 'application/octet-stream')
    response['Content-Length'] = str(att.size)
    # Allow inline viewing for images and PDFs; force download for other types
    if att.content_type:
        if att.content_type.startswith('image/') or att.content_type == 'application/pdf':
            response['Content-Disposition'] = f'inline; filename="{att.filename}"'
        else:
            response['Content-Disposition'] = f'attachment; filename="{att.filename}"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{att.filename}"'
    return response


@login_required
@require_http_methods(["GET"])
def download_group_message_attachment_thumbnail(request, attachment_id):
    att = get_object_or_404(GroupMessageAttachment, pk=attachment_id)
    group = att.message.group
    if not group.is_member(request.user):
        raise Http404('Not found')
    data = att.get_thumbnail_content()
    if data is None:
        raise Http404('Thumbnail not available')
    response = HttpResponse(data, content_type='image/png')
    response['Content-Length'] = str(len(data))
    response['Content-Disposition'] = f'inline; filename="{att.filename}.png"'
    return response
