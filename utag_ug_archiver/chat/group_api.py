"""
Group Management API Endpoints
Handles adding/removing members, promoting members, updating group info, etc.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Q
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from accounts.models import User
from chat.models import ChatGroup, GroupMembership
import json
import logging

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def get_available_members(request, group_id):
    """Get users who are not yet members of the group"""
    try:
        group = get_object_or_404(ChatGroup, pk=group_id)
        
        # Security: Ensure user is a group member
        if not group.is_member(request.user):
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        # Get current member IDs
        current_member_ids = group.members.values_list('id', flat=True)
        
        # Get all users except current members and current user
        available_users = User.objects.exclude(
            Q(id__in=current_member_ids) | Q(id=request.user.id)
        ).values('id', 'other_name', 'surname', 'title', 'executive_position')
        
        members_list = []
        for user in available_users:
            initials = f"{user.get('other_name', '?')[0]}{user.get('surname', '?')[0]}".upper()
            members_list.append({
                'id': user['id'],
                'name': f"{user.get('title', '')} {user.get('other_name', '')} {user.get('surname', '')}".strip(),
                'initials': initials,
                'position': user.get('executive_position') or 'Member'
            })
        
        return JsonResponse({'success': True, 'members': members_list})
    except Exception as e:
        logger.error(f"Error fetching available members: {e}")
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_POST
def add_members_to_group(request, group_id):
    """Add new members to a group"""
    try:
        group = get_object_or_404(ChatGroup, pk=group_id)
        
        # Security: Ensure user is a group admin
        membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not membership or not membership.is_admin:
            return JsonResponse({'success': False, 'error': 'Only admins can add members'}, status=403)
        
        # Parse request body
        try:
            data = json.loads(request.body)
            member_ids = data.get('member_ids', [])
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
        
        if not member_ids:
            return JsonResponse({'success': False, 'error': 'No members selected'}, status=400)
        
        # Add members
        added_count = 0
        for user_id in member_ids:
            try:
                user = User.objects.get(pk=user_id)
                GroupMembership.objects.get_or_create(
                    group=group,
                    user=user,
                    defaults={'added_by': request.user, 'is_admin': False}
                )
                added_count += 1
            except User.DoesNotExist:
                continue
            except IntegrityError:
                continue
        
        return JsonResponse({
            'success': True,
            'message': f'{added_count} member(s) added successfully'
        })
    except Exception as e:
        logger.error(f"Error adding members: {e}")
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_POST
def remove_member_from_group(request, group_id, member_id):
    """Remove a member from a group"""
    try:
        group = get_object_or_404(ChatGroup, pk=group_id)
        
        # Security: Ensure user is a group admin
        admin_membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not admin_membership or not admin_membership.is_admin:
            return JsonResponse({'success': False, 'error': 'Only admins can remove members'}, status=403)
        
        # Get the membership to remove
        membership = get_object_or_404(GroupMembership, pk=member_id, group=group)
        
        # Prevent removing yourself
        if membership.user == request.user:
            return JsonResponse({'success': False, 'error': 'Cannot remove yourself'}, status=400)
        
        # Prevent removing other admins (optional - you can change this logic)
        if membership.is_admin:
            return JsonResponse({'success': False, 'error': 'Cannot remove other admins'}, status=400)
        
        membership.delete()
        
        return JsonResponse({'success': True, 'message': 'Member removed successfully'})
    except Exception as e:
        logger.error(f"Error removing member: {e}")
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_POST
def promote_group_member(request, group_id, member_id):
    """Promote a member to moderator or admin"""
    try:
        group = get_object_or_404(ChatGroup, pk=group_id)
        
        # Security: Ensure user is a group admin
        admin_membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not admin_membership or not admin_membership.is_admin:
            return JsonResponse({'success': False, 'error': 'Only admins can promote members'}, status=403)
        
        # Parse request body
        try:
            data = json.loads(request.body)
            new_role = data.get('role', 'member')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
        
        # Get the membership to promote
        membership = get_object_or_404(GroupMembership, pk=member_id, group=group)
        
        # Update role
        if new_role == 'admin':
            membership.is_admin = True
        else:
            membership.is_admin = False
        
        membership.save()
        
        return JsonResponse({'success': True, 'message': 'Member promoted successfully'})
    except Exception as e:
        logger.error(f"Error promoting member: {e}")
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_POST
def update_group_info(request, group_id):
    """Update group name and other info"""
    try:
        group = get_object_or_404(ChatGroup, pk=group_id)
        
        # Security: Ensure user is a group admin
        membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not membership or not membership.is_admin:
            return JsonResponse({'success': False, 'error': 'Only admins can edit group info'}, status=403)
        
        # Parse request body
        try:
            data = json.loads(request.body)
            new_name = data.get('name', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)
        
        if not new_name:
            return JsonResponse({'success': False, 'error': 'Group name cannot be empty'}, status=400)
        
        group.name = new_name
        group.save()
        
        return JsonResponse({'success': True, 'message': 'Group updated successfully'})
    except Exception as e:
        logger.error(f"Error updating group: {e}")
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_POST
def leave_group(request, group_id):
    """Leave a group"""
    try:
        group = get_object_or_404(ChatGroup, pk=group_id)
        
        # Get user's membership
        membership = GroupMembership.objects.filter(group=group, user=request.user).first()
        if not membership:
            return JsonResponse({'success': False, 'error': 'You are not a member of this group'}, status=400)
        
        # Check if user is the last admin
        admin_count = GroupMembership.objects.filter(group=group, is_admin=True).count()
        if membership.is_admin and admin_count == 1:
            return JsonResponse({
                'success': False,
                'error': 'You are the last admin. Please promote another member before leaving.'
            }, status=400)
        
        membership.delete()
        
        return JsonResponse({'success': True, 'message': 'Left group successfully'})
    except Exception as e:
        logger.error(f"Error leaving group: {e}")
        return JsonResponse({'success': False, 'error': 'An error occurred'}, status=500)


@login_required
@require_http_methods(["GET"])
def join_group_via_link(request, token):
    """Join a group via encrypted invite link token with proper user feedback"""
    try:
        group = get_object_or_404(ChatGroup, invite_token=token)
        
        # Check if already a member
        if group.is_member(request.user):
            messages.warning(request, f'You are already a member of "{group.name}"')
            return redirect('chat:group_detail', pk=group.id)
        
        # Try to add user to group
        try:
            membership, created = GroupMembership.objects.get_or_create(
                group=group,
                user=request.user,
                defaults={'is_admin': False}
            )
            
            if created:
                messages.success(
                    request, 
                    f'🎉 Successfully joined "{group.name}"! Welcome to the group.'
                )
                logger.info(f"User {request.user.id} joined group {group.id} via invite link")
            else:
                messages.info(request, f'You are now a member of "{group.name}"')
            
            return redirect('chat:group_detail', pk=group.id)
        
        except IntegrityError:
            # User was added between check and create
            messages.info(request, f'You are now a member of "{group.name}"')
            return redirect('chat:group_detail', pk=group.id)
    
    except ChatGroup.DoesNotExist:
        messages.error(request, '❌ Group not found. The invite link may be invalid or expired.')
        logger.warning(f"User {request.user.id} tried to join via invalid token")
        return redirect('chat:thread_list')
    
    except Exception as e:
        logger.error(f"Error joining group: {e}")
        messages.error(
            request, 
            '❌ An error occurred while joining the group. Please try again.'
        )
        return redirect('chat:thread_list')
