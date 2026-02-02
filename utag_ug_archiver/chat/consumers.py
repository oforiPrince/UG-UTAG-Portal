"""
Secure WebSocket consumers for chat functionality with authentication and authorization.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import Http404

from .models import ChatThread, ChatGroup, Message, GroupMessage

User = get_user_model()
logger = logging.getLogger(__name__)


@database_sync_to_async
def get_user(user_id):
    """Get user by ID, ensuring they are active."""
    try:
        return User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return None


@database_sync_to_async
def get_thread_and_validate_access(thread_id, user):
    """
    Get thread and validate user has access.
    Security: Ensures user is a participant before allowing WebSocket connection.
    """
    try:
        thread_id = int(thread_id)
    except (ValueError, TypeError):
        raise ValueError('Invalid thread ID')
    
    try:
        thread = ChatThread.objects.select_related('user_one', 'user_two').get(pk=thread_id)
    except ChatThread.DoesNotExist:
        raise Http404('Thread not found')
    
    # Security: Verify user is a participant
    if not thread.is_participant(user):
        raise PermissionError('Access denied: User is not a participant of this thread')
    
    return thread


@database_sync_to_async
def get_group_and_validate_access(group_id, user):
    """
    Get group and validate user has access.
    Security: Ensures user is a member before allowing WebSocket connection.
    """
    try:
        group_id = int(group_id)
    except (ValueError, TypeError):
        raise ValueError('Invalid group ID')
    
    try:
        group = ChatGroup.objects.prefetch_related('members').get(pk=group_id)
    except ChatGroup.DoesNotExist:
        raise Http404('Group not found')
    
    # Security: Verify user is a member
    if not group.is_member(user):
        raise PermissionError('Access denied: User is not a member of this group')
    
    return group


@database_sync_to_async
def save_direct_message(thread, sender, message_text, reply_to_id=None):
    """
    Save a direct message with encryption.
    Security: Validates message length and ensures sender is thread participant.
    """
    # Security: Validate message length
    if not message_text or len(message_text.strip()) == 0:
        raise ValidationError('Message cannot be empty')
    
    if len(message_text) > 2000:
        raise ValidationError('Message too long (max 2000 characters)')
    
    # Security: Verify sender is participant
    if not thread.is_participant(sender):
        raise PermissionError('Sender is not a participant of this thread')
    
    # Create and save encrypted message
    message = Message(thread=thread, sender=sender)
    # If reply_to_id provided, try to attach referenced message (must belong to same thread)
    if reply_to_id is not None:
        try:
            ref = Message.objects.get(pk=int(reply_to_id), thread=thread)
            message.reply_to = ref
        except (Message.DoesNotExist, ValueError):
            # ignore invalid reply reference
            pass

    message.set_plaintext(message_text.strip())
    message.save()
    
    # Note: Don't mark as read here - messages start unread for recipient
    # They will be marked read when recipient views the thread
    
    return message


@database_sync_to_async
def save_direct_delivery(message_id, user):
    """Record a delivery ack for a direct message from a recipient."""
    try:
        msg = Message.objects.get(pk=int(message_id))
    except Exception:
        return None
    # Do not create delivery for sender
    if msg.sender_id == user.id:
        return None
    try:
        from .models import MessageDelivery
        delivery, created = MessageDelivery.objects.get_or_create(message=msg, user=user)
        return {
            'message_id': msg.id,
            'user_id': user.id,
            'user_name': user.get_full_name(),
            'avatar_url': user.get_profile_pic_url(),
            'delivered_at': delivery.delivered_at.isoformat()
        }
    except Exception:
        return None


@database_sync_to_async
def save_group_message(group, sender, message_text, reply_to_id=None):
    """
    Save a group message with encryption.
    Security: Validates message length and ensures sender is group member.
    """
    # Security: Validate message length
    if not message_text or len(message_text.strip()) == 0:
        raise ValidationError('Message cannot be empty')
    
    if len(message_text) > 2000:
        raise ValidationError('Message too long (max 2000 characters)')
    
    # Security: Verify sender is member
    if not group.is_member(sender):
        raise PermissionError('Sender is not a member of this group')
    
    # Create and save encrypted message
    message = GroupMessage(group=group, sender=sender)
    # If reply_to_id provided, try to attach referenced group message
    if reply_to_id is not None:
        try:
            ref = GroupMessage.objects.get(pk=int(reply_to_id), group=group)
            message.reply_to = ref
        except (GroupMessage.DoesNotExist, ValueError):
            pass

    message.set_plaintext(message_text.strip())
    message.save()
    
    # Mark as read for sender
    message.mark_read_for(sender)
    
    return message


@database_sync_to_async
def save_group_delivery(message_id, user):
    """Record a delivery ack for a group message from a recipient."""
    try:
        msg = GroupMessage.objects.get(pk=int(message_id))
    except Exception:
        return None
    if msg.sender_id == user.id:
        return None
    try:
        from .models import GroupMessageDelivery
        delivery, created = GroupMessageDelivery.objects.get_or_create(message=msg, user=user)
        return {
            'message_id': msg.id,
            'user_id': user.id,
            'user_name': user.get_full_name(),
            'avatar_url': user.get_profile_pic_url(),
            'delivered_at': delivery.delivered_at.isoformat()
        }
    except Exception:
        return None


@database_sync_to_async
def mark_thread_messages_read(thread, user):
    """Mark all unread messages in thread as read for user."""
    thread.mark_messages_as_read(user)


@database_sync_to_async
def mark_group_messages_read(group, user):
    """Mark all unread group messages as read for user."""
    unread = group.messages.exclude(sender=user).exclude(read_by=user)
    for msg in unread:
        msg.mark_read_for(user)


async def broadcast_chat_list_update(channel_layer, user_ids, chat_data):
    """
    Broadcast chat list update to specified users.
    
    Args:
        channel_layer: Channels layer instance
        user_ids: List of user IDs to notify
        chat_data: Dict containing chat update info (id, type, last_message, etc.)
    """
    for user_id in user_ids:
        await channel_layer.group_send(
            f'chat_list_{user_id}',
            {
                'type': 'chat_list_update',
                'chat': chat_data
            }
        )


@database_sync_to_async
def get_thread_chat_data(thread, user):
    """Get formatted chat data for thread to send to chat list."""
    other_user = thread.other_participant(user)
    last_msg = thread.messages.order_by('-created_at').first() if thread.messages.exists() else None
    
    # Calculate unread count for this specific user
    from django.db.models import Q, Count
    unread_count = thread.messages.filter(
        Q(read_at__isnull=True) & ~Q(sender=user)
    ).count()
    
    return {
        'id': thread.id,
        'access_token': thread.access_token,
        'is_group': False,
        'display_name': f"{other_user.title} {other_user.other_name} {other_user.surname}" if other_user else 'Unknown User',
        'avatar_initials': f"{other_user.other_name[0]}{other_user.surname[0]}" if other_user else '?',
        'profile_pic_url': other_user.profile_pic.url if (other_user and other_user.profile_pic) else None,
        'last_message': last_msg.plaintext if last_msg else '',
        'last_message_time': (thread.last_message_at or thread.created_at).isoformat(),
        'unread_count': unread_count,
    }


@database_sync_to_async
def get_group_chat_data(group, user):
    """Get formatted chat data for group to send to chat list."""
    last_msg = group.messages.order_by('-created_at').first() if group.messages.exists() else None
    
    # Calculate unread count for this specific user
    from django.db.models import Q, Count
    unread_count = group.messages.filter(
        ~Q(read_by=user) & ~Q(sender=user)
    ).count()
    
    return {
        'id': group.id,
        'access_token': group.access_token,
        'is_group': True,
        'display_name': group.name,
        'avatar_initials': group.name[0].upper() if group.name else 'G',
        'profile_pic_url': None,  # Groups don't have profile pics
        'last_message': last_msg.plaintext if last_msg else '',
        'last_message_time': (last_msg.created_at if last_msg else group.created_at).isoformat(),
        'unread_count': unread_count,
    }


class ThreadChatConsumer(AsyncWebsocketConsumer):
    """
    Secure WebSocket consumer for direct message threads.
    Implements authentication, authorization, and message encryption.
    """
    
    async def connect(self):
        """
        Handle WebSocket connection.
        Security: Validates user authentication and thread access.
        """
        # Get authenticated user from scope
        self.user = self.scope.get('user')
        
        # Security: Require authenticated user
        if not self.user or not self.user.is_authenticated:
            logger.warning(f'Unauthenticated WebSocket connection attempt to thread')
            await self.close(code=4001)  # Unauthorized
            return
        
        # Security: Ensure user is active
        if not self.user.is_active:
            logger.warning(f'Inactive user {self.user.id} attempted WebSocket connection')
            await self.close(code=4003)  # Forbidden
            return
        
        # Get thread_id from URL
        self.thread_id = self.scope['url_route']['kwargs']['thread_id']
        
        try:
            # Security: Validate thread access
            self.thread = await get_thread_and_validate_access(self.thread_id, self.user)
        except (ValueError, Http404) as e:
            logger.warning(f'Invalid thread access attempt: {e} by user {self.user.id}')
            await self.close(code=4004)  # Not Found
            return
        except PermissionError as e:
            logger.warning(f'Unauthorized thread access attempt: {e} by user {self.user.id}')
            await self.close(code=4003)  # Forbidden
            return
        except Exception as e:
            logger.error(f'Error validating thread access: {e}')
            await self.close(code=4000)  # Internal Error
            return
        
        # Join thread group for broadcasting
        self.room_group_name = f'thread_{self.thread_id}'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Mark messages as read when user connects
        try:
            await mark_thread_messages_read(self.thread, self.user)
        except Exception as e:
            logger.error(f'Error marking messages as read: {e}')
        
        logger.info(f'User {self.user.id} connected to thread {self.thread_id}')
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        logger.info(f'User {self.user.id if hasattr(self, "user") else "Unknown"} disconnected from thread {self.thread_id if hasattr(self, "thread_id") else "Unknown"}')
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket message.
        Security: Validates message content and sender authorization.
        """
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': 'Invalid JSON format'
            }))
            return
        
        message_type = data.get('type')
        
        if message_type == 'message':
            # Security: Validate message content
            message_text = data.get('message', '').strip()
            reply_to_id = data.get('reply_to')
            
            if not message_text:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error': 'Message cannot be empty'
                }))
                return
            
            try:
                # Save message with encryption (support reply_to)
                message = await save_direct_message(self.thread, self.user, message_text, reply_to_id=reply_to_id)
                
                # Get other participant for display
                other_user = self.thread.other_participant(self.user)
                
                # Broadcast message to thread group
                # Prepare reply payload if present
                reply_payload = None
                if getattr(message, 'reply_to_id', None):
                    try:
                        reply_payload = {
                            'id': message.reply_to_id,
                            'body': message.reply_to.plaintext
                        }
                    except Exception:
                        reply_payload = None

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': {
                            'id': message.id,
                            'body': message.plaintext,
                            'sender_id': message.sender_id,
                            'sender_name': self.user.get_full_name(),
                            'created_at': message.created_at.isoformat(),
                            'read_at': message.read_at.isoformat() if message.read_at else None,
                            'reply_to': reply_payload,
                        }
                    }
                )
                
                # Broadcast chat list update to both participants
                chat_data_sender = await get_thread_chat_data(self.thread, self.user)
                chat_data_recipient = await get_thread_chat_data(self.thread, other_user)
                await broadcast_chat_list_update(
                    self.channel_layer,
                    [self.user.id, other_user.id],
                    chat_data_sender  # We'll send individual updates in a moment
                )
                # Actually send personalized updates
                await self.channel_layer.group_send(
                    f'chat_list_{self.user.id}',
                    {'type': 'chat_list_update', 'chat': chat_data_sender}
                )
                await self.channel_layer.group_send(
                    f'chat_list_{other_user.id}',
                    {'type': 'chat_list_update', 'chat': chat_data_recipient}
                )
                
            except ValidationError as e:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error': str(e)
                }))
            except PermissionError as e:
                logger.warning(f'Permission denied for message send: {e} by user {self.user.id}')
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error': 'Permission denied'
                }))
            except Exception as e:
                logger.error(f'Error saving message: {e}')
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error': 'Failed to save message'
                }))
        
        elif message_type == 'typing':
            # Broadcast typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'user_id': self.user.id,
                    'user_name': self.user.get_full_name(),
                    'is_typing': data.get('is_typing', False)
                }
            )
        elif message_type == 'delivered':
            # Recipient reports it has received the message; record and broadcast delivery
            message_id = data.get('message_id')
            try:
                res = await save_direct_delivery(message_id, self.user)
                if res:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'delivery',
                            'delivery': res,
                        }
                    )
            except Exception as e:
                logger.exception('Error handling delivered ack')
        
        else:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': f'Unknown message type: {message_type}'
            }))
    
    async def chat_message(self, event):
        """Send message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))

    async def delivery(self, event):
        """Forward delivery events to WebSocket clients."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'delivery',
                'delivery': event.get('delivery')
            }))
        except Exception:
            logger.exception('Error sending delivery event')
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket."""
        # Don't send typing indicator to the user who is typing
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))

    async def read_receipt(self, event):
        """Forward read receipt events to WebSocket clients."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'read',
                'user_id': event.get('user_id'),
                'message_ids': event.get('message_ids', [])
            }))
        except Exception:
            logger.exception('Error sending group read receipt')

    async def read_receipt(self, event):
        """Forward read receipt events to WebSocket clients."""
        # send read event to clients (other side will update UI)
        try:
            await self.send(text_data=json.dumps({
                'type': 'read',
                'user_id': event.get('user_id'),
                'message_ids': event.get('message_ids', [])
            }))
        except Exception as e:
            logger.exception('Error sending read receipt over websocket')


class GroupChatConsumer(AsyncWebsocketConsumer):
    """
    Secure WebSocket consumer for group chats.
    Implements authentication, authorization, and message encryption.
    """
    
    async def connect(self):
        """
        Handle WebSocket connection.
        Security: Validates user authentication and group membership.
        """
        # Get authenticated user from scope
        self.user = self.scope.get('user')
        
        # Security: Require authenticated user
        if not self.user or not self.user.is_authenticated:
            logger.warning(f'Unauthenticated WebSocket connection attempt to group')
            await self.close(code=4001)  # Unauthorized
            return
        
        # Security: Ensure user is active
        if not self.user.is_active:
            logger.warning(f'Inactive user {self.user.id} attempted WebSocket connection')
            await self.close(code=4003)  # Forbidden
            return
        
        # Get group_id from URL
        self.group_id = self.scope['url_route']['kwargs']['group_id']
        
        try:
            # Security: Validate group access
            self.group = await get_group_and_validate_access(self.group_id, self.user)
        except (ValueError, Http404) as e:
            logger.warning(f'Invalid group access attempt: {e} by user {self.user.id}')
            await self.close(code=4004)  # Not Found
            return
        except PermissionError as e:
            logger.warning(f'Unauthorized group access attempt: {e} by user {self.user.id}')
            await self.close(code=4003)  # Forbidden
            return
        except Exception as e:
            logger.error(f'Error validating group access: {e}')
            await self.close(code=4000)  # Internal Error
            return
        
        # Join group room for broadcasting
        self.room_group_name = f'group_{self.group_id}'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Mark messages as read when user connects
        try:
            await mark_group_messages_read(self.group, self.user)
        except Exception as e:
            logger.error(f'Error marking messages as read: {e}')
        
        logger.info(f'User {self.user.id} connected to group {self.group_id}')
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        logger.info(f'User {self.user.id if hasattr(self, "user") else "Unknown"} disconnected from group {self.group_id if hasattr(self, "group_id") else "Unknown"}')
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket message.
        Security: Validates message content and sender authorization.
        """
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': 'Invalid JSON format'
            }))
            return
        
        message_type = data.get('type')
        
        if message_type == 'message':
            # Security: Validate message content
            message_text = data.get('message', '').strip()
            reply_to_id = data.get('reply_to')
            
            if not message_text:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error': 'Message cannot be empty'
                }))
                return
            
            try:
                # Save message with encryption (support reply_to)
                message = await save_group_message(self.group, self.user, message_text, reply_to_id=reply_to_id)
                
                # Broadcast message to group
                # Prepare reply payload if present
                reply_payload = None
                if getattr(message, 'reply_to_id', None):
                    try:
                        reply_payload = {
                            'id': message.reply_to_id,
                            'body': message.reply_to.plaintext
                        }
                    except Exception:
                        reply_payload = None

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': {
                            'id': message.id,
                            'body': message.plaintext,
                            'sender_id': message.sender_id,
                            'sender_name': self.user.get_full_name(),
                            'created_at': message.created_at.isoformat(),
                            'reply_to': reply_payload,
                        }
                    }
                )
                
                # Broadcast chat list update to all group members
                from .models import ChatGroup
                group_obj = await database_sync_to_async(ChatGroup.objects.prefetch_related('members').get)(pk=self.group_id)
                member_ids = await database_sync_to_async(list)(group_obj.members.values_list('id', flat=True))
                
                # Send personalized updates to each member with their own unread count
                for member_id in member_ids:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    member = await database_sync_to_async(User.objects.get)(pk=member_id)
                    chat_data = await get_group_chat_data(self.group, member)
                    await self.channel_layer.group_send(
                        f'chat_list_{member_id}',
                        {'type': 'chat_list_update', 'chat': chat_data}
                    )
                
            except ValidationError as e:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error': str(e)
                }))
            except PermissionError as e:
                logger.warning(f'Permission denied for message send: {e} by user {self.user.id}')
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error': 'Permission denied'
                }))
            except Exception as e:
                logger.error(f'Error saving message: {e}')
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error': 'Failed to save message'
                }))
        
        elif message_type == 'typing':
            # Broadcast typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'user_id': self.user.id,
                    'user_name': self.user.get_full_name(),
                    'is_typing': data.get('is_typing', False)
                }
            )
        elif message_type == 'delivered':
            # Recipient reports it has received the message; record and broadcast delivery
            message_id = data.get('message_id')
            try:
                res = await save_group_delivery(message_id, self.user)
                if res:
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'delivery',
                            'delivery': res,
                        }
                    )
            except Exception:
                logger.exception('Error handling delivered ack (group)')
        
        else:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': f'Unknown message type: {message_type}'
            }))
    
    async def chat_message(self, event):
        """Send message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message']
        }))
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket."""
        # Don't send typing indicator to the user who is typing
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing']
            }))

    async def delivery(self, event):
        """Forward delivery events to WebSocket clients."""
        try:
            await self.send(text_data=json.dumps({
                'type': 'delivery',
                'delivery': event.get('delivery')
            }))
        except Exception:
            logger.exception('Error sending group delivery event')


class ChatListConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat list updates.
    Broadcasts new messages to update chat list without page reload.
    """
    
    async def connect(self):
        """Accept connection if user is authenticated."""
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return
        
        # Each user has their own chat list channel
        self.room_group_name = f'chat_list_{self.user.id}'
        
        # Join user's personal chat list group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f'Chat list WebSocket connected for user {self.user.id}')
    
    async def disconnect(self, close_code):
        """Leave chat list group."""
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            logger.info(f'Chat list WebSocket disconnected for user {self.user.id}')
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages (e.g., ping/pong for keepalive)."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except json.JSONDecodeError:
            logger.warning('Invalid JSON received in chat list WebSocket')
    
    async def chat_list_update(self, event):
        """
        Send chat list update to WebSocket.
        Event should contain: chat_id, chat_type, last_message, timestamp, unread_count
        """
        await self.send(text_data=json.dumps({
            'type': 'chat_update',
            'chat': event['chat']
        }))

