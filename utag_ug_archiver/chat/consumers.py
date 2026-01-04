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
def save_direct_message(thread, sender, message_text):
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
    message.set_plaintext(message_text.strip())
    message.save()
    
    # Mark as read for sender
    message.mark_as_read()
    
    return message


@database_sync_to_async
def save_group_message(group, sender, message_text):
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
    message.set_plaintext(message_text.strip())
    message.save()
    
    # Mark as read for sender
    message.mark_read_for(sender)
    
    return message


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
            
            if not message_text:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error': 'Message cannot be empty'
                }))
                return
            
            try:
                # Save message with encryption
                message = await save_direct_message(self.thread, self.user, message_text)
                
                # Get other participant for display
                other_user = self.thread.other_participant(self.user)
                
                # Broadcast message to thread group
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
                        }
                    }
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
            
            if not message_text:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error': 'Message cannot be empty'
                }))
                return
            
            try:
                # Save message with encryption
                message = await save_group_message(self.group, self.user, message_text)
                
                # Broadcast message to group
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
                        }
                    }
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

