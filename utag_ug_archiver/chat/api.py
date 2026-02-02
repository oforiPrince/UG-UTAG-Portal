from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.db import IntegrityError
from accounts.models import User
from chat.models import ChatThread, ChatGroup, GroupMembership, Message, GroupMessage
import json
import logging
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from chat.models import MessageAttachment, GroupMessageAttachment
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import uuid
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from .models import ChatGroupInvite

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def get_users_list(request):
    """
    API endpoint to get list of users for direct chat or group creation
    Excludes the current user
    Security: Only returns active users, excludes sensitive information
    """
    # Security: Exclude current user and get users, exclude sensitive fields
    users = User.objects.exclude(
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
            'url': f'/chat/thread/{thread.access_token}/',
            'redirect_url': f'/chat/thread/{thread.access_token}/'
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
                'url': f'/chat/group/{existing.access_token}/',
                'redirect_url': f'/chat/group/{existing.access_token}/',
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
                    'url': f'/chat/group/{existing.access_token}/',
                    'redirect_url': f'/chat/group/{existing.access_token}/',
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
                # Security: Get user and validate they exist
                user = User.objects.get(id=member_id)
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
            'url': f'/chat/group/{group.access_token}/',
            'redirect_url': f'/chat/group/{group.access_token}/',
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

        # Determine unread message ids (exclude messages sent by requester)
        from chat.models import Message as ChatMessage
        unread_qs = ChatMessage.objects.filter(thread=thread).exclude(sender=request.user).filter(read_at__isnull=True)
        message_ids = list(unread_qs.values_list('id', flat=True))

        # Mark as read
        thread.mark_messages_as_read(request.user)

        # Broadcast read receipt to thread group
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer and message_ids:
                async_to_sync(channel_layer.group_send)(
                    f'thread_{thread_id}',
                    {
                        'type': 'read_receipt',
                        'user_id': request.user.id,
                        'message_ids': message_ids,
                    }
                )
        except Exception:
            logger.exception('Failed to broadcast thread read receipt')

        return JsonResponse({'success': True, 'read_count': len(message_ids), 'message_ids': message_ids})
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

        # Collect unread message ids
        unread_qs = group.messages.exclude(sender=request.user).exclude(read_by=request.user)
        message_ids = list(unread_qs.values_list('id', flat=True))
        for msg in unread_qs:
            msg.mark_read_for(request.user)

        # Broadcast read receipt to group
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer and message_ids:
                async_to_sync(channel_layer.group_send)(
                    f'group_{group_id}',
                    {
                        'type': 'read_receipt',
                        'user_id': request.user.id,
                        'message_ids': message_ids,
                    }
                )
        except Exception:
            logger.exception('Failed to broadcast group read receipt')

        return JsonResponse({'success': True, 'read_count': len(message_ids), 'message_ids': message_ids})
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_POST
def remove_group_member(request, group_id):
    try:
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid group ID'}, status=400)

        group = get_object_or_404(ChatGroup, pk=group_id)

        # Only group creator or admins can remove members
        if not group.can_manage_members(request.user):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        user_id = request.POST.get('user_id')
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid user ID'}, status=400)

        membership = GroupMembership.objects.filter(group=group, user_id=user_id).first()
        if not membership:
            return JsonResponse({'success': False, 'error': 'Member not found'}, status=404)

        # Prevent removing the creator
        if group.created_by_id == membership.user_id:
            return JsonResponse({'success': False, 'error': 'Cannot remove group creator'}, status=400)

        membership.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        logger.exception('Error removing group member')
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_POST
def toggle_group_admin(request, group_id):
    try:
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid group ID'}, status=400)

        group = get_object_or_404(ChatGroup, pk=group_id)

        # Only creator or superuser can toggle admins
        if not (request.user == group.created_by or request.user.is_superuser):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        user_id = request.POST.get('user_id')
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid user ID'}, status=400)

        membership = GroupMembership.objects.filter(group=group, user_id=user_id).first()
        if not membership:
            return JsonResponse({'success': False, 'error': 'Member not found'}, status=404)

        # Toggle is_admin
        membership.is_admin = not bool(membership.is_admin)
        membership.save(update_fields=['is_admin'])
        return JsonResponse({'success': True, 'is_admin': membership.is_admin})
    except Exception as e:
        logger.exception('Error toggling admin')
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_POST
def create_group_invite(request, group_id):
    try:
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid group ID'}, status=400)

        group = get_object_or_404(ChatGroup, pk=group_id)

        # Only group admins can create invites
        if not group.can_manage_members(request.user):
            return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

        # Optional expiry in minutes
        expiry_minutes = request.POST.get('expires_in')
        expires_at = None
        if expiry_minutes:
            try:
                mins = int(expiry_minutes)
                expires_at = timezone.now() + timedelta(minutes=mins)
            except Exception:
                expires_at = None

        token = uuid.uuid4().hex
        invite = ChatGroupInvite.objects.create(group=group, token=token, created_by=request.user, expires_at=expires_at)
        invite_url = request.build_absolute_uri(f'/chat/group/invite/{invite.token}/')
        return JsonResponse({'success': True, 'invite_url': invite_url, 'token': invite.token})
    except Exception as e:
        logger.exception('Error creating invite')
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def accept_group_invite(request, token):
    try:
        invite = get_object_or_404(ChatGroupInvite, token=token)
        if not invite.is_valid():
            return JsonResponse({'success': False, 'error': 'Invite expired'}, status=400)

        group = invite.group
        # Add user as member if not already
        if not GroupMembership.objects.filter(group=group, user=request.user).exists():
            GroupMembership.objects.create(group=group, user=request.user, added_by=invite.created_by)
        return JsonResponse({'success': True, 'group_id': group.id, 'redirect_url': f'/chat/group/{group.access_token}/'})
    except Exception as e:
        logger.exception('Error accepting invite')
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_POST
def delete_message(request):
    """Delete a message by id. Accepts 'message_id' and optional 'type' ('direct'|'group')."""
    try:
        message_id = request.POST.get('message_id')
        mtype = request.POST.get('type', 'direct')
        try:
            message_id = int(message_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid message id'}, status=400)

        if mtype == 'group':
            msg = get_object_or_404(GroupMessage, pk=message_id)
            group = msg.group
            # Only group admins, group creator, message sender or superuser can delete
            is_allowed = (group.can_manage_members(request.user) or msg.sender == request.user or request.user.is_superuser)
            if not is_allowed:
                return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
            msg.delete()
            return JsonResponse({'success': True})
        else:
            msg = get_object_or_404(Message, pk=message_id)
            thread = msg.thread
            # Only sender or superuser can delete direct messages
            if not (msg.sender == request.user or request.user.is_superuser):
                return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
            msg.delete()
            return JsonResponse({'success': True})
    except Exception as e:
        logger.exception('Error deleting message')
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
