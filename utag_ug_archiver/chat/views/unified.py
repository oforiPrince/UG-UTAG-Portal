"""Unified conversation view for both direct and group chats"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View

from ..forms import DirectMessageForm, GroupMessageForm
from ..models import ChatGroup, ChatThread, GroupMessage, Message
from ..models import MessageAttachment, GroupMessageAttachment
from django.http import HttpResponse, FileResponse
from django.shortcuts import redirect
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

# Maximum attachment size in bytes (default 20 MB)
MAX_ATTACHMENT_SIZE = getattr(settings, 'CHAT_MAX_ATTACHMENT_SIZE', 20 * 1024 * 1024)


class UnifiedConversationView(LoginRequiredMixin, View):
    """Unified view for both direct chats and group conversations"""
    template_name = 'chat/modern_conversation.html'

    def get_context(self, request, chat_type, pk):
        """Get context data for the conversation
        Security: Validates chat_type, pk/token, and user access before returning context
        For direct chats: pk is access_token (string)
        For groups: pk is access_token (string)
        """
        # Security: Validate chat_type
        if chat_type not in ['direct', 'group']:
            raise Http404('Invalid chat type')
        
        context = {'chat_type': chat_type}
        
        if chat_type == 'direct':
            # For direct chats, pk is the access_token (string)
            thread = get_object_or_404(ChatThread, access_token=pk)
            
            # Security: Ensure user is participant
            if not thread.is_participant(request.user):
                raise Http404('You do not have access to this conversation.')
            
            thread.mark_messages_as_read(request.user)
            other_user = thread.other_participant(request.user)
            
            context.update({
                'thread': thread,
                'other_user': other_user,
                'message_list': thread.messages.select_related('sender').prefetch_related('attachments').order_by('created_at'),
                'form': DirectMessageForm(),
            })
            
        elif chat_type == 'group':
            # For groups, pk is the access_token (string)
            group = get_object_or_404(ChatGroup, access_token=pk)
            
            # Security: Ensure user is a group member
            if not group.is_member(request.user):
                raise Http404('You are not a member of this group.')
            
            # Mark messages as read - add user to read_by for unread messages
            unread_messages = group.messages.exclude(sender=request.user).exclude(read_by=request.user)
            for msg in unread_messages:
                msg.mark_read_for(request.user)
            
            context.update({
                'group': group,
                'group_invite_token': group.invite_token,  # Token for sharing invite link
                'message_list': group.messages.select_related('sender').prefetch_related('attachments').order_by('created_at'),
                'form': GroupMessageForm(),
            })
            # Build members list with full membership info including role
            members = []
            for m in group.members.all():
                try:
                    gm = group.membership_records.get(user=m)
                    members.append({
                        'id': gm.id,  # Membership ID for API calls
                        'user': m,
                        'role': 'admin' if gm.is_admin else 'member',
                        'is_admin': bool(gm.is_admin)
                    })
                except Exception:
                    members.append({
                        'id': None,
                        'user': m,
                        'role': 'member',
                        'is_admin': False
                    })
            context['members'] = members
            
            # Check if current user is admin
            try:
                user_membership = group.membership_records.get(user=request.user)
                context['user_is_admin'] = user_membership.is_admin
            except Exception:
                context['user_is_admin'] = False
        
        return context

    def get(self, request, chat_type, pk):
        """Handle GET request"""
        context = self.get_context(request, chat_type, pk)
        return render(request, self.template_name, context)

    def post(self, request, chat_type, pk):
        """Handle POST request (sending messages)
        Security: Validates chat_type, pk/token, user access, message content, and attachment size
        For direct chats: pk is access_token (string)
        For groups: pk is access_token (string)
        """
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Security: Validate chat_type
        if chat_type not in ['direct', 'group']:
            if is_ajax:
                return JsonResponse({'success': False, 'error': 'Invalid chat type'}, status=400)
            raise Http404('Invalid chat type')
        
        if chat_type == 'direct':
            # For direct chats, pk is the access_token (string)
            thread = get_object_or_404(ChatThread, access_token=pk)
            
            # Security: Ensure user is participant
            if not thread.is_participant(request.user):
                if is_ajax:
                    return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
                raise Http404('You do not have access to this conversation.')
            
            form = DirectMessageForm(request.POST, request.FILES)
            if form.is_valid():
                # Security: Validate message length
                body = form.cleaned_data['body'].strip()
                if len(body) > 2000:
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': 'Message too long'}, status=400)
                    from django.contrib import messages
                    messages.error(request, 'Message too long')
                    return render(request, self.template_name, self.get_context(request, chat_type, pk))
                
                message = Message(thread=thread, sender=request.user)
                message.set_plaintext(body)
                message.save()

                # Security: Handle optional attachment with validation
                attachment = form.cleaned_data.get('attachment')
                attachments_info = []
                if attachment:
                    # Security: Server-side size check
                    if isinstance(attachment, UploadedFile) and attachment.size > MAX_ATTACHMENT_SIZE:
                        if is_ajax:
                            return JsonResponse({'success': False, 'error': f'Attachment too large. Maximum size is {MAX_ATTACHMENT_SIZE // (1024*1024)}MB'}, status=400)
                        from django.contrib import messages
                        messages.error(request, f'Attachment too large. Maximum size is {MAX_ATTACHMENT_SIZE // (1024*1024)}MB')
                        return render(request, self.template_name, self.get_context(request, chat_type, pk))
                    
                    # Security: Validate file type (optional - can be enhanced)
                    # Security: Sanitize filename
                    import os
                    safe_filename = os.path.basename(attachment.name)
                    
                    try:
                        att = MessageAttachment(message=message, filename=safe_filename, content_type=attachment.content_type or 'application/octet-stream')
                        data = attachment.read()
                        att.set_content(data)
                        att.save()
                        attachments_info.append({
                            'id': att.id,
                            'filename': att.filename,
                            'size': att.size,
                            'url': att.download_url(),
                            'content_type': att.content_type,
                        })
                    except Exception as e:
                        if is_ajax:
                            return JsonResponse({'success': False, 'error': 'Failed to save attachment'}, status=500)
                        from django.contrib import messages
                        messages.error(request, 'Failed to save attachment')
                        return render(request, self.template_name, self.get_context(request, chat_type, pk))
                
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'message': {
                            'id': message.id,
                            'body': message.plaintext,
                            'plaintext': message.plaintext,
                            'sender_id': message.sender_id,
                            'created_at': message.created_at.isoformat(),
                            'read_at': message.read_at.isoformat() if message.read_at else None,
                            'attachments': attachments_info,
                        }
                    })
                
                return render(request, self.template_name, self.get_context(request, chat_type, pk))
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid message',
                    'errors': form.errors
                }, status=400)
                
        elif chat_type == 'group':
            # For groups, pk is the access_token (string)
            group = get_object_or_404(ChatGroup, access_token=pk)
            
            # Security: Ensure user is a group member
            if not group.is_member(request.user):
                if is_ajax:
                    return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
                raise Http404('You are not a member of this group.')
            
            form = GroupMessageForm(request.POST, request.FILES)
            if form.is_valid():
                # Security: Validate message length
                body = form.cleaned_data['body'].strip()
                if len(body) > 2000:
                    if is_ajax:
                        return JsonResponse({'success': False, 'error': 'Message too long'}, status=400)
                    from django.contrib import messages
                    messages.error(request, 'Message too long')
                    return render(request, self.template_name, self.get_context(request, chat_type, pk))
                
                message = GroupMessage(group=group, sender=request.user)
                message.set_plaintext(body)
                message.save()

                # Security: Handle attachments with validation
                attachments_info = []
                attachment = form.cleaned_data.get('attachment')
                if attachment:
                    # Security: Server-side size check
                    if isinstance(attachment, UploadedFile) and attachment.size > MAX_ATTACHMENT_SIZE:
                        if is_ajax:
                            return JsonResponse({'success': False, 'error': f'Attachment too large. Maximum size is {MAX_ATTACHMENT_SIZE // (1024*1024)}MB'}, status=400)
                        from django.contrib import messages
                        messages.error(request, f'Attachment too large. Maximum size is {MAX_ATTACHMENT_SIZE // (1024*1024)}MB')
                        return render(request, self.template_name, self.get_context(request, chat_type, pk))
                    
                    # Security: Sanitize filename
                    import os
                    safe_filename = os.path.basename(attachment.name)
                    
                    try:
                        att = GroupMessageAttachment(message=message, filename=safe_filename, content_type=attachment.content_type or 'application/octet-stream')
                        data = attachment.read()
                        att.set_content(data)
                        att.save()
                        attachments_info.append({
                            'id': att.id,
                            'filename': att.filename,
                            'size': att.size,
                            'url': att.download_url(),
                            'content_type': att.content_type,
                        })
                    except Exception as e:
                        if is_ajax:
                            return JsonResponse({'success': False, 'error': 'Failed to save attachment'}, status=500)
                        from django.contrib import messages
                        messages.error(request, 'Failed to save attachment')
                        return render(request, self.template_name, self.get_context(request, chat_type, pk))
                
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'message': {
                            'id': message.id,
                            'body': message.plaintext,
                            'plaintext': message.plaintext,
                            'sender_id': message.sender_id,
                            'sender_name': message.sender.get_full_name(),
                            'created_at': message.created_at.isoformat(),
                            'attachments': attachments_info,
                        }
                    })
                
                return render(request, self.template_name, self.get_context(request, chat_type, pk))
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid message',
                    'errors': form.errors
                }, status=400)
        
        # If we get here, something went wrong
        context = self.get_context(request, chat_type, pk)
        return render(request, self.template_name, context)
