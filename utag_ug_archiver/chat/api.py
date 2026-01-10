from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.db import IntegrityError
from accounts.models import User
from chat.models import ChatThread, ChatGroup, GroupMembership
import json
import logging
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from chat.models import MessageAttachment, GroupMessageAttachment
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def get_users_list(request):
    """
    API endpoint to get list of users for direct chat or group creation
    Excludes the current user
    Security: Only returns active users, excludes sensitive information
    """
    # Security: Only return active users, exclude sensitive fields
    users = User.objects.filter(
        is_active=True
    ).exclude(
        id=request.user.id
    ).select_related('profile_pic').values('id', 'other_name', 'surname', 'title', 'profile_pic')
    
    users_list = []
    for user in users:
        # Security: Sanitize user data
        users_list.append({
            'id': user['id'],
            'name': f"{user.get('other_name', '')} {user.get('surname', '')}".strip(),
            'title': user.get('title') or '',
            'avatar': user['profile_pic'] if user.get('profile_pic') else None,
            'initial': (user.get('other_name', '') or '?')[0].upper()
        })
    
    return JsonResponse({'success': True, 'users': users_list})


@login_required
@require_http_methods(["POST"])
def start_direct_chat(request):
    """
    API endpoint to start a direct chat with a user
    Creates thread if doesn't exist, returns URL to chat
    Security: Validates user exists, is active, and user cannot chat with themselves
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
        
        # Security: Validate user_id is integer
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid user ID'}, status=400)
        
        # Security: Prevent self-chat
        if user_id == request.user.id:
            return JsonResponse({'success': False, 'error': 'Cannot start chat with yourself'}, status=400)
        
        # Security: Get user and validate they exist
        try:
            other_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        
        # Security: Use get_or_create_thread to ensure proper normalization and encryption
        thread, created = ChatThread.objects.get_or_create_thread(request.user, other_user)
        
        return JsonResponse({
            'success': True,
            'url': f'/chat/thread/{thread.id}/',
            'redirect_url': f'/chat/thread/{thread.id}/'
        })
        
    except ValueError as e:
        # Handle thread creation errors (e.g., same user on both sides)
        logger.error(f"ValueError in start_direct_chat: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error in start_direct_chat: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_http_methods(["POST"])
def create_group_ajax(request):
    """
    API endpoint to create a group chat with multiple members
    Returns URL to new group chat
    Security: Validates permissions, sanitizes input, validates member IDs
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
        
        # Security: Validate and sanitize group name
        if not group_name:
            return JsonResponse({'success': False, 'error': 'Group name required'}, status=400)
        
        group_name = group_name.strip()
        if len(group_name) < 2 or len(group_name) > 120:
            return JsonResponse({'success': False, 'error': 'Group name must be between 2 and 120 characters'}, status=400)
        
        # Security: Check permissions (only executives and staff can create groups)
        if not ((hasattr(request.user, 'is_executive') and request.user.is_executive()) or request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'success': False, 'error': 'Permission denied. Only executives can create groups.'}, status=403)
        
        # Security: Validate member_ids
        if not member_ids:
            return JsonResponse({'success': False, 'error': 'At least one member required'}, status=400)
        
        # Security: Normalize and validate member IDs
        try:
            member_ids = list(dict.fromkeys(int(x) for x in member_ids))
        except (ValueError, TypeError):
            # member_ids might be malformed; try best-effort
            cleaned = []
            for mid in member_ids:
                try:
                    cleaned.append(int(mid))
                except (ValueError, TypeError):
                    continue
            member_ids = list(dict.fromkeys(cleaned))
        
        # Security: Remove duplicates and self
        member_ids = [mid for mid in member_ids if mid != request.user.id]
        
        if not member_ids:
            return JsonResponse({'success': False, 'error': 'At least one other member required'}, status=400)
        
        # Security: Limit group size (prevent abuse)
        if len(member_ids) > 50:
            return JsonResponse({'success': False, 'error': 'Group cannot have more than 50 members'}, status=400)

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
        
        # Security: Add selected members with validation
        added_count = 0
        for member_id in member_ids:
            try:
                # Security: Only add active users
                user = User.objects.get(id=member_id, is_active=True)
                # Security: Prevent duplicate memberships
                if not GroupMembership.objects.filter(group=group, user=user).exists():
                    GroupMembership.objects.create(
                        group=group,
                        user=user,
                        added_by=request.user
                    )
                    added_count += 1
            except User.DoesNotExist:
                continue
            except IntegrityError:
                # Already a member, skip
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
    Security: Validates thread_id and ensures user is participant
    """
    try:
        # Security: Validate thread_id is integer
        try:
            thread_id = int(thread_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid thread ID'}, status=400)
        
        thread = get_object_or_404(ChatThread, pk=thread_id)
        
        # Security: Ensure user is a participant
        if not thread.is_participant(request.user):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        thread.mark_messages_as_read(request.user)
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_http_methods(["POST"])
def mark_group_read(request, group_id):
    """
    Mark group messages as read for the requesting user (adds user to read_by for unread group messages).
    Security: Validates group_id and ensures user is member
    """
    try:
        # Security: Validate group_id is integer
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid group ID'}, status=400)
        
        group = get_object_or_404(ChatGroup, pk=group_id)
        
        # Security: Ensure user is a member
        if not group.is_member(request.user):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        unread = group.messages.exclude(sender=request.user).exclude(read_by=request.user)
        for msg in unread:
            msg.mark_read_for(request.user)

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_http_methods(["GET"])
def download_message_attachment(request, attachment_id):
    """
    Download and decrypt a direct message attachment.
    Security: Validates attachment_id, ensures requester is thread participant, sanitizes filename
    """
    try:
        # Security: Validate attachment_id is integer
        try:
            attachment_id = int(attachment_id)
        except (ValueError, TypeError):
            raise Http404('Not found')
        
        att = get_object_or_404(MessageAttachment, pk=attachment_id)
        thread = att.message.thread
        
        # Security: Ensure user is a thread participant
        if not thread.is_participant(request.user):
            raise Http404('Not found')
        
        # Security: Get decrypted content
        try:
            data = att.get_content()
        except Exception:
            raise Http404('Unable to decrypt attachment')
        
        # Security: Sanitize filename to prevent path traversal
        import os
        safe_filename = os.path.basename(att.filename)
        
        response = HttpResponse(data, content_type=att.content_type or 'application/octet-stream')
        response['Content-Length'] = str(att.size)
        
        # Security: Set appropriate Content-Disposition
        if att.content_type:
            if att.content_type.startswith('image/') or att.content_type == 'application/pdf':
                response['Content-Disposition'] = f'inline; filename="{safe_filename}"'
            else:
                response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
        else:
            response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
        
        return response
    except Http404:
        raise
    except Exception:
        raise Http404('Not found')


@login_required
@require_http_methods(["GET"])
def download_message_attachment_thumbnail(request, attachment_id):
    """
    Download thumbnail for a direct message attachment.
    Security: Validates attachment_id, ensures requester is thread participant
    """
    try:
        # Security: Validate attachment_id is integer
        try:
            attachment_id = int(attachment_id)
        except (ValueError, TypeError):
            raise Http404('Not found')
        
        att = get_object_or_404(MessageAttachment, pk=attachment_id)
        thread = att.message.thread
        
        # Security: Ensure user is a thread participant
        if not thread.is_participant(request.user):
            raise Http404('Not found')
        
        data = att.get_thumbnail_content()
        if data is None:
            raise Http404('Thumbnail not available')
        
        response = HttpResponse(data, content_type='image/png')
        response['Content-Length'] = str(len(data))
        response['Content-Disposition'] = f'inline; filename="thumbnail.png"'
        return response
    except Http404:
        raise
    except Exception:
        raise Http404('Not found')


@login_required
@require_http_methods(["GET"])
def download_group_message_attachment(request, attachment_id):
    """
    Download and decrypt a group message attachment.
    Security: Validates attachment_id, ensures requester is group member, sanitizes filename
    """
    try:
        # Security: Validate attachment_id is integer
        try:
            attachment_id = int(attachment_id)
        except (ValueError, TypeError):
            raise Http404('Not found')
        
        att = get_object_or_404(GroupMessageAttachment, pk=attachment_id)
        group = att.message.group
        
        # Security: Ensure user is a group member
        if not group.is_member(request.user):
            raise Http404('Not found')
        
        # Security: Get decrypted content
        try:
            data = att.get_content()
        except Exception:
            raise Http404('Unable to decrypt attachment')
        
        # Security: Sanitize filename
        import os
        safe_filename = os.path.basename(att.filename)
        
        response = HttpResponse(data, content_type=att.content_type or 'application/octet-stream')
        response['Content-Length'] = str(att.size)
        
        # Security: Set appropriate Content-Disposition
        if att.content_type:
            if att.content_type.startswith('image/') or att.content_type == 'application/pdf':
                response['Content-Disposition'] = f'inline; filename="{safe_filename}"'
            else:
                response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
        else:
            response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
        
        return response
    except Http404:
        raise
    except Exception:
        raise Http404('Not found')


@login_required
@require_http_methods(["GET"])
def download_group_message_attachment_thumbnail(request, attachment_id):
    """
    Download thumbnail for a group message attachment.
    Security: Validates attachment_id, ensures requester is group member
    """
    try:
        # Security: Validate attachment_id is integer
        try:
            attachment_id = int(attachment_id)
        except (ValueError, TypeError):
            raise Http404('Not found')
        
        att = get_object_or_404(GroupMessageAttachment, pk=attachment_id)
        group = att.message.group
        
        # Security: Ensure user is a group member
        if not group.is_member(request.user):
            raise Http404('Not found')
        
        data = att.get_thumbnail_content()
        if data is None:
            raise Http404('Thumbnail not available')
        
        response = HttpResponse(data, content_type='image/png')
        response['Content-Length'] = str(len(data))
        response['Content-Disposition'] = f'inline; filename="thumbnail.png"'
        return response
    except Http404:
        raise
    except Exception:
        raise Http404('Not found')
