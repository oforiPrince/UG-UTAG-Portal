from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Max, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from ..forms import (
    DirectMessageForm,
    GroupCreateForm,
    GroupMemberAddForm,
    GroupMessageForm,
    ThreadStartForm,
)
from ..models import ChatGroup, ChatThread, GroupMembership, GroupMessage, Message


class ThreadListView(LoginRequiredMixin, ListView):
    """View to display all chat threads and groups for the current user"""
    model = ChatThread
    template_name = 'chat/simple_list.html'
    context_object_name = 'threads'

    def get(self, request, *args, **kwargs):
        from accounts.models import User
        
        # Get direct message threads (where user is either user_one or user_two)
        threads = ChatThread.objects.filter(
            Q(user_one=request.user) | Q(user_two=request.user)
        ).select_related('user_one', 'user_two').annotate(
            last_message_time=Max('messages__created_at'),
            unread_count=Count(
                'messages',
                filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=request.user)
            )
        ).order_by('-last_message_time')

        # Get group chats the user is a member of
        groups = ChatGroup.objects.filter(
            members=request.user
        ).prefetch_related('members').annotate(
            last_message_time=Max('messages__created_at'),
            unread_count=Count(
                'messages',
                filter=~Q(messages__read_by=request.user) & ~Q(messages__sender=request.user)
            )
        ).order_by('-last_message_time')

        # Combine and normalize both types for the simple interface
        chats = []
        
        # Add direct threads
        for thread in threads:
            other_user = thread.other_participant(request.user)
            last_msg = thread.messages.order_by('-created_at').first() if thread.messages.exists() else None
            
            chats.append({
                'id': thread.id,
                'is_group': False,
                'display_name': f"{other_user.title} {other_user.other_name} {other_user.surname}" if other_user else 'Unknown User',
                'avatar_initials': f"{other_user.other_name[0]}{other_user.surname[0]}" if other_user else '?',
                'last_message': last_msg.plaintext if last_msg else '',
                'last_message_time': thread.last_message_time or thread.created_at,
                'unread_count': thread.unread_count,
            })
        
        # Add groups
        for group in groups:
            last_msg = group.messages.order_by('-created_at').first() if group.messages.exists() else None
            
            chats.append({
                'id': group.id,
                'is_group': True,
                'display_name': group.name,
                'avatar_initials': group.name[0].upper() if group.name else 'G',
                'last_message': last_msg.plaintext if last_msg else '',
                'last_message_time': group.last_message_time or group.created_at,
                'unread_count': group.unread_count,
            })
        
        # Sort all chats by last activity
        chats.sort(key=lambda x: x['last_message_time'], reverse=True)
        
        # Get all users except current user for the modal
        available_users = User.objects.exclude(id=request.user.id).order_by('other_name', 'surname')
        
        context = {
            'chats': chats,
            'available_users': available_users,
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
            if created:
                messages.success(request, 'Chat thread created successfully.')
            else:
                messages.info(request, 'You already had a conversation with this member. We took you there.')
            return redirect('chat:thread_detail', pk=thread.pk)
        return render(request, self.template_name, {'form': form})


class ThreadDetailView(LoginRequiredMixin, View):
    template_name = 'chat/thread_detail.html'

    def get_thread(self, user, pk):
        thread = get_object_or_404(ChatThread, pk=pk)
        if not thread.is_participant(user):
            raise Http404('You do not have access to this conversation.')
        return thread

    def resolve_other_user(self, thread, user):
        try:
            return thread.other_participant(user)
        except ValueError as exc:
            raise Http404('You do not have access to this conversation.') from exc

    def get(self, request, pk):
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
        
        thread = self.get_thread(request.user, pk)
        form = DirectMessageForm(request.POST)
        
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
            messages.success(request, 'Message sent.')
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
    template_name = 'chat/group_create_enhanced.html'

    def dispatch(self, request, *args, **kwargs):
        # Allow executives and admins to create groups
        if not (hasattr(request.user, 'is_executive') and (request.user.is_executive or request.user.is_staff)):
            messages.error(request, 'Only executives and administrators can create groups.')
            return redirect('chat:thread_list')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        form = GroupCreateForm(creator=request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = GroupCreateForm(creator=request.user, data=request.POST)
        if form.is_valid():
            # Create the group
            group = ChatGroup.objects.create(
                name=form.cleaned_data['name'], 
                created_by=request.user
            )
            
            # Add creator as member
            GroupMembership.objects.create(
                group=group, 
                user=request.user, 
                added_by=request.user
            )
            
            # Add selected members
            selected_members = form.cleaned_data.get('members', [])
            for member in selected_members:
                GroupMembership.objects.create(
                    group=group,
                    user=member,
                    added_by=request.user
                )
            
            member_count = selected_members.count() if selected_members else 0
            messages.success(
                request, 
                f'Group "{group.name}" created successfully with {member_count + 1} member(s)!'
            )
            return redirect('chat:group_detail', pk=group.pk)
        return render(request, self.template_name, {'form': form})


class GroupDetailView(LoginRequiredMixin, View):
    template_name = 'chat/group_detail.html'

    def get_group(self, user, pk):
        group = get_object_or_404(ChatGroup, pk=pk)
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
        group = self.get_group(request.user, pk)
        form = GroupMessageForm(request.POST)
        if form.is_valid():
            message = GroupMessage(group=group, sender=request.user)
            message.set_plaintext(form.cleaned_data['body'])
            message.save()
            message.read_by.add(request.user)
            messages.success(request, 'Message shared with the group.')
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
        self.group = get_object_or_404(ChatGroup, pk=pk)
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
            GroupMembership.objects.create(group=self.group, user=user, added_by=request.user)
            messages.success(request, f'{user.get_full_name()} added to the group.')
            return redirect('chat:group_detail', pk=self.group.pk)
        return render(request, self.template_name, {'form': form, 'group': self.group})
