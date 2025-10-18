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
    template_name = 'chat/simple_conversation.html'

    def get_context(self, request, chat_type, pk):
        """Get context data for the conversation"""
        context = {'chat_type': chat_type}
        
        if chat_type == 'direct':
            thread = get_object_or_404(ChatThread, pk=pk)
            if not thread.is_participant(request.user):
                raise Http404('You do not have access to this conversation.')
            
            thread.mark_messages_as_read(request.user)
            other_user = thread.other_participant(request.user)
            
            context.update({
                'thread': thread,
                'other_user': other_user,
                'messages': thread.messages.select_related('sender').prefetch_related('attachments').order_by('created_at'),
                'form': DirectMessageForm(),
            })
            
        elif chat_type == 'group':
            group = get_object_or_404(ChatGroup, pk=pk)
            if not group.members.filter(id=request.user.id).exists():
                raise Http404('You are not a member of this group.')
            
            # Mark messages as read - add user to read_by for unread messages
            unread_messages = group.messages.exclude(sender=request.user).exclude(read_by=request.user)
            for msg in unread_messages:
                msg.read_by.add(request.user)
            
            context.update({
                'group': group,
                'messages': group.messages.select_related('sender').prefetch_related('attachments').order_by('created_at'),
                'form': GroupMessageForm(),
            })
        
        return context

    def get(self, request, chat_type, pk):
        """Handle GET request"""
        context = self.get_context(request, chat_type, pk)
        return render(request, self.template_name, context)

    def post(self, request, chat_type, pk):
        """Handle POST request (sending messages)"""
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if chat_type == 'direct':
            thread = get_object_or_404(ChatThread, pk=pk)
            if not thread.is_participant(request.user):
                raise Http404('You do not have access to this conversation.')
            
            form = DirectMessageForm(request.POST, request.FILES)
            if form.is_valid():
                message = Message(thread=thread, sender=request.user)
                message.set_plaintext(form.cleaned_data['body'])
                message.save()

                # handle optional attachment
                attachment = form.cleaned_data.get('attachment')
                attachments_info = []
                if attachment:
                    # server-side size check
                    if isinstance(attachment, UploadedFile) and attachment.size > MAX_ATTACHMENT_SIZE:
                        if is_ajax:
                            return JsonResponse({'success': False, 'error': 'Attachment too large'}, status=400)
                        messages.error(request, 'Attachment too large')
                        return render(request, self.template_name, self.get_context(request, chat_type, pk))
                    att = MessageAttachment(message=message, filename=attachment.name, content_type=attachment.content_type)
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
                
                messages.success(request, 'Message sent.')
                return render(request, self.template_name, self.get_context(request, chat_type, pk))
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid message',
                    'errors': form.errors
                }, status=400)
                
        elif chat_type == 'group':
            group = get_object_or_404(ChatGroup, pk=pk)
            if not group.members.filter(id=request.user.id).exists():
                raise Http404('You are not a member of this group.')
            
            form = GroupMessageForm(request.POST, request.FILES)
            if form.is_valid():
                message = GroupMessage(group=group, sender=request.user)
                message.set_plaintext(form.cleaned_data['body'])
                message.save()

                attachments_info = []
                attachment = form.cleaned_data.get('attachment')
                if attachment:
                    if isinstance(attachment, UploadedFile) and attachment.size > MAX_ATTACHMENT_SIZE:
                        if is_ajax:
                            return JsonResponse({'success': False, 'error': 'Attachment too large'}, status=400)
                        messages.error(request, 'Attachment too large')
                        return render(request, self.template_name, self.get_context(request, chat_type, pk))
                    att = GroupMessageAttachment(message=message, filename=attachment.name, content_type=attachment.content_type)
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
                
                messages.success(request, 'Message sent.')
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
