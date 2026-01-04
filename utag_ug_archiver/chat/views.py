from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from .forms import (
    DirectMessageForm,
    GroupCreateForm,
    GroupMemberAddForm,
    GroupMessageForm,
    ThreadStartForm,
)
from .models import ChatGroup, ChatThread, GroupMembership, GroupMessage, Message
from .views.unified import UnifiedConversationView


class ThreadListView(LoginRequiredMixin, ListView):
    """View to display all chat threads and groups for the current user"""
    model = ChatThread
    template_name = 'chat/unified_list.html'
    context_object_name = 'threads'

    def get(self, request, *args, **kwargs):
        # Get direct message threads
        threads = ChatThread.objects.filter(participants=request.user).annotate(
            last_message_time=Max('message__created_at'),
            unread_count=Count(
                'message',
                filter=Q(message__read_at__isnull=True) & ~Q(message__sender=request.user)
            )
        ).order_by('-last_message_time')

        # Get group chats the user is a member of
        groups = ChatGroup.objects.filter(
            members=request.user
        ).annotate(
            last_message_time=Max('groupmessage__created_at'),
            unread_count=Count(
                'groupmessage',
                filter=Q(groupmessage__groupmessageread__is_read=False, groupmessage__groupmessageread__user=request.user)
            )
        ).order_by('-last_message_time')

        # Combine and normalize both types
        chats = []
        
        # Add direct threads
        for thread in threads:
            other_user = thread.get_other_user(request.user)
            last_msg = thread.message_set.first() if thread.message_set.exists() else None
            chats.append({
                'type': 'direct',
                'name': other_user.get_full_name() if other_user else 'Unknown User',
                'avatar': other_user.profile_pic.url if other_user and other_user.profile_pic else None,
                'avatar_initial': other_user.first_name[0].upper() if other_user and other_user.first_name else '?',
                'subtitle': other_user.title if other_user and hasattr(other_user, 'title') else '',
                'url': reverse('chat:thread_detail', kwargs={'pk': thread.pk}),
                'unread_count': thread.unread_count,
                'updated_at': thread.last_message_time or thread.created_at,
                'last_message': last_msg,
            })
        
        # Add groups
        for group in groups:
            last_msg = group.groupmessage_set.first() if group.groupmessage_set.exists() else None
            chats.append({
                'type': 'group',
                'name': group.name,
                'avatar': None,
                'avatar_initial': group.name[0].upper() if group.name else 'G',
                'subtitle': f"{group.members.count()} members",
                'url': reverse('chat:group_detail', kwargs={'pk': group.pk}),
                'unread_count': group.unread_count,
                'updated_at': group.last_message_time or group.created_at,
                'last_message': last_msg,
            })
        
        # Sort all chats by last activity
        chats.sort(key=lambda x: x['updated_at'], reverse=True)
        
        # Check if user can create groups (executives only)
        can_create_groups = (
            hasattr(request.user, 'is_executive') and request.user.is_executive
        ) or request.user.is_staff
        
        context = {
            'chats': chats,
            'can_create_groups': can_create_groups
        }
        
        return render(request, self.template_name, context)


class ThreadStartView(LoginRequiredMixin, View):
    template_name = 'chat/thread_start.html'

    def get(self, request):
        form = ThreadStartForm(request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = ThreadStartForm(request.user, request.POST)
        if form.is_valid():
            recipient = form.cleaned_data['recipient']
            message_text = form.cleaned_data['initial_message'].strip()
            thread, created = ChatThread.objects.get_or_create_thread(request.user, recipient)
            if message_text:
                message = Message(thread=thread, sender=request.user)
                message.set_plaintext(message_text)
                message.save()
            return redirect('chat:thread_detail', pk=thread.pk)
        return render(request, self.template_name, {'form': form})


class ThreadDetailView(LoginRequiredMixin, View):
    template_name = 'chat/thread_detail.html'

    def get_thread(self, user, pk):
        # Security: Validate pk is integer
        try:
            pk = int(pk)
        except (ValueError, TypeError):
            raise Http404('Invalid thread ID')
        
        thread = get_object_or_404(ChatThread, pk=pk)
        
        # Security: Ensure user is participant
        if not thread.is_participant(user):
            raise Http404('You do not have access to this conversation.')
        return thread

    def resolve_other_user(self, thread, user):
        try:
            return thread.other_participant(user)
        except ValueError as exc:
            raise Http404('You do not have access to this conversation.') from exc

    def get(self, request, pk):
        # Security: Validate pk is integer
        try:
            pk = int(pk)
        except (ValueError, TypeError):
            raise Http404('Invalid thread ID')
        
        thread = self.get_thread(request.user, pk)
        thread.mark_messages_as_read(request.user)
        form = DirectMessageForm()
        context = {
            'thread': thread,
            'form': form,
            'message_list': thread.messages.select_related('sender'),
            'other_user': self.resolve_other_user(thread, request.user),
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        from django.http import JsonResponse
        
        # Security: Validate pk is integer
        try:
            pk = int(pk)
        except (ValueError, TypeError):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Invalid thread ID'}, status=400)
            raise Http404('Invalid thread ID')
        
        thread = self.get_thread(request.user, pk)
        form = DirectMessageForm(request.POST)
        
        # Security: Validate message content
        if form.is_valid():
            body = form.cleaned_data['body'].strip()
            if len(body) > 2000:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': 'Message too long'}, status=400)
                from django.contrib import messages
                messages.error(request, 'Message too long')
                return render(request, self.template_name, {
                    'thread': thread,
                    'form': form,
                    'message_list': thread.messages.select_related('sender'),
                    'other_user': self.resolve_other_user(thread, request.user),
                })
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if form.is_valid():
                message = Message(thread=thread, sender=request.user)
                message.set_plaintext(form.cleaned_data['body'])
                message.save()
                return JsonResponse({
                    'success': True,
                    'message': {
                        'id': message.id,
                        'body': message.plaintext,
                        'sender_id': message.sender_id,
                        'created_at': message.created_at.isoformat(),
                        'read_at': message.read_at.isoformat() if message.read_at else None,
                    }
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid message',
                    'errors': form.errors
                }, status=400)
        
        # Handle regular form submission
        if form.is_valid():
            message = Message(thread=thread, sender=request.user)
            message.set_plaintext(form.cleaned_data['body'])
            message.save()
            return redirect(reverse('chat:thread_detail', kwargs={'pk': thread.pk}))
        
        context = {
            'thread': thread,
            'form': form,
            'message_list': thread.messages.select_related('sender'),
            'other_user': self.resolve_other_user(thread, request.user),
        }
        return render(request, self.template_name, context)


class GroupListView(LoginRequiredMixin, View):
    template_name = 'chat/group_list.html'

    def get(self, request):
        groups = ChatGroup.objects.filter(members=request.user).order_by('name')
        return render(
            request,
            self.template_name,
            {
                'groups': groups,
                'can_create_groups': request.user.is_executive() or request.user.is_superuser,
            },
        )


class GroupCreateView(LoginRequiredMixin, View):
    template_name = 'chat/group_create.html'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_executive() or request.user.is_superuser):
            raise Http404('You are not permitted to create executive groups.')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = GroupCreateForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = GroupCreateForm(request.POST)
        if form.is_valid():
            group = ChatGroup.objects.create(name=form.cleaned_data['name'], created_by=request.user)
            GroupMembership.objects.create(group=group, user=request.user, added_by=request.user)
            return redirect('chat:group_detail', pk=group.pk)
        return render(request, self.template_name, {'form': form})


class GroupDetailView(LoginRequiredMixin, View):
    template_name = 'chat/group_detail.html'

    def get_group(self, user, pk):
        # Security: Validate pk is integer
        try:
            pk = int(pk)
        except (ValueError, TypeError):
            raise Http404('Invalid group ID')
        
        group = get_object_or_404(ChatGroup, pk=pk)
        
        # Security: Ensure user is a group member
        if not group.is_member(user):
            raise Http404('You are not part of this group.')
        return group

    def get(self, request, pk):
        group = self.get_group(request.user, pk)
        form = GroupMessageForm()
        member_form = None
        if group.can_manage_members(request.user):
            member_form = GroupMemberAddForm(group)
        unread_messages = group.messages.exclude(read_by=request.user).exclude(sender=request.user)
        for message in unread_messages:
            message.mark_read_for(request.user)
        context = {
            'group': group,
            'form': form,
            'message_list': group.messages.select_related('sender'),
            'member_form': member_form,
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        # Security: Validate pk is integer
        try:
            pk = int(pk)
        except (ValueError, TypeError):
            raise Http404('Invalid group ID')
        
        group = self.get_group(request.user, pk)
        form = GroupMessageForm(request.POST)
        if form.is_valid():
            # Security: Validate message length
            body = form.cleaned_data['body'].strip()
            if len(body) > 2000:
                from django.contrib import messages
                messages.error(request, 'Message too long')
                return render(request, self.template_name, {
                    'group': group,
                    'form': form,
                    'message_list': group.messages.select_related('sender'),
                    'member_form': GroupMemberAddForm(group) if group.can_manage_members(request.user) else None,
                })
            
            message = GroupMessage(group=group, sender=request.user)
            message.set_plaintext(body)
            message.save()
            message.mark_read_for(request.user)
            return redirect(reverse('chat:group_detail', kwargs={'pk': group.pk}))
        member_form = GroupMemberAddForm(group) if group.can_manage_members(request.user) else None
        context = {
            'group': group,
            'form': form,
            'message_list': group.messages.select_related('sender'),
            'member_form': member_form,
        }
        return render(request, self.template_name, context)


class GroupMemberAddView(LoginRequiredMixin, View):
    template_name = 'chat/group_add_member.html'

    def dispatch(self, request, pk, *args, **kwargs):
        # Security: Validate pk is integer
        try:
            pk = int(pk)
        except (ValueError, TypeError):
            raise Http404('Invalid group ID')
        
        self.group = get_object_or_404(ChatGroup, pk=pk)
        
        # Security: Ensure user can manage members
        if not self.group.can_manage_members(request.user):
            raise Http404('You do not have permission to manage this group.')
        return super().dispatch(request, pk, *args, **kwargs)

    def get(self, request, pk):
        form = GroupMemberAddForm(self.group)
        return render(request, self.template_name, {'form': form, 'group': self.group})

    def post(self, request, pk):
        form = GroupMemberAddForm(self.group, request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            
            # Security: Prevent duplicate memberships
            if GroupMembership.objects.filter(group=self.group, user=user).exists():
                from django.contrib import messages
                messages.error(request, 'User is already a member of this group.')
                return render(request, self.template_name, {'form': form, 'group': self.group})
            
            # Security: Only add active users
            if not user.is_active:
                from django.contrib import messages
                messages.error(request, 'Cannot add inactive user to group.')
                return render(request, self.template_name, {'form': form, 'group': self.group})
            
            GroupMembership.objects.create(group=self.group, user=user, added_by=request.user)
            from django.contrib import messages
            messages.success(request, f'{user.get_full_name()} has been added to the group.')
            return redirect('chat:group_detail', pk=self.group.pk)
        return render(request, self.template_name, {'form': form, 'group': self.group})
