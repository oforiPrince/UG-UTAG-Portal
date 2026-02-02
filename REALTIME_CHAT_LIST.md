# Real-Time Chat List Updates

## Overview
The chat list now updates in real-time using WebSocket connections. When a new message is sent in any chat (individual or group), all participants see the update immediately without needing to refresh the page.

## Implementation

### 1. WebSocket Consumer (`ChatListConsumer`)
**File**: `chat/consumers.py`

A new consumer handles chat list updates:
- Each user connects to their personal channel: `chat_list_{user_id}`
- Broadcasts include updated chat information with personalized unread counts
- Supports ping/pong for connection keepalive

```python
class ChatListConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = f'chat_list_{self.user.id}'
        # Join personal chat list group
    
    async def chat_list_update(self, event):
        # Send chat update to WebSocket
```

### 2. WebSocket Routing
**File**: `chat/routing.py`

New route added:
```python
path('ws/chat/list/', ChatListConsumer.as_asgi(), name='chat_list_ws')
```

### 3. Broadcast Updates
**Files**: `chat/consumers.py`

#### Individual Chats (ThreadChatConsumer)
When a message is sent in a thread:
1. Message is saved and broadcasted to thread participants
2. **NEW**: Chat list update is sent to both participants with their personalized unread counts

```python
# Send personalized updates
chat_data_sender = await get_thread_chat_data(self.thread, self.user)
chat_data_recipient = await get_thread_chat_data(self.thread, other_user)
await self.channel_layer.group_send(
    f'chat_list_{self.user.id}',
    {'type': 'chat_list_update', 'chat': chat_data_sender}
)
await self.channel_layer.group_send(
    f'chat_list_{other_user.id}',
    {'type': 'chat_list_update', 'chat': chat_data_recipient}
)
```

#### Group Chats (GroupChatConsumer)
When a message is sent in a group:
1. Message is saved and broadcasted to group members
2. **NEW**: Chat list update is sent to ALL group members with personalized unread counts

```python
# Send personalized updates to each member
for member_id in member_ids:
    member = await database_sync_to_async(User.objects.get)(pk=member_id)
    chat_data = await get_group_chat_data(self.group, member)
    await self.channel_layer.group_send(
        f'chat_list_{member_id}',
        {'type': 'chat_list_update', 'chat': chat_data}
    )
```

### 4. Frontend WebSocket Client
**File**: `chat/templates/chat/simple_list_modern.html`

JavaScript implementation:
- Connects to `ws://host/ws/chat/list/` on page load
- Auto-reconnects if connection drops (max 5 attempts)
- Sends ping every 30 seconds for keepalive
- Updates chat items when messages arrive
- Moves updated chats to top of list
- Shows/updates unread badges

```javascript
function connectChatListWebSocket() {
    const wsUrl = `${protocol}//${window.location.host}/ws/chat/list/`;
    chatListSocket = new WebSocket(wsUrl);
    
    chatListSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        if (data.type === 'chat_update') {
            updateChatInList(data.chat);
        }
    };
}
```

### 5. Helper Functions

#### `get_thread_chat_data(thread, user)`
Returns formatted chat data for individual thread:
- Display name, avatar, profile picture
- Last message and timestamp
- **Personalized unread count** (different for each participant)

#### `get_group_chat_data(group, user)`
Returns formatted chat data for group:
- Group name, avatar initials
- Last message and timestamp
- **Personalized unread count** (different for each member)

## Features

### ✅ Real-Time Updates
- New messages appear instantly in chat list
- No page refresh required
- Chats automatically reorder by recent activity

### ✅ Personalized Unread Counts
- Each user sees their own unread count
- Sender sees 0 unread (they sent the message)
- Recipients see accurate unread counts

### ✅ Automatic Reconnection
- WebSocket auto-reconnects if disconnected
- Max 5 reconnection attempts
- 3-second delay between attempts

### ✅ Connection Keepalive
- Ping/pong every 30 seconds
- Prevents timeout on idle connections

### ✅ Smooth UX
- Chat moves to top when new message arrives
- Unread badge updates dynamically
- Profile pictures display correctly
- Timestamps update to relative format

## Data Flow

### Individual Chat Message
```
User A sends message
    ↓
ThreadChatConsumer.receive()
    ↓
Save message to database
    ↓
Broadcast to thread participants (User A & User B)
    ↓
Broadcast chat list update:
  - User A: unread_count = 0 (sender)
  - User B: unread_count = 1 (recipient)
    ↓
Frontend updates chat list UI
```

### Group Chat Message
```
User A sends message to Group
    ↓
GroupChatConsumer.receive()
    ↓
Save message to database
    ↓
Broadcast to all group members
    ↓
For each member:
  - Calculate personalized unread count
  - Send chat list update
    ↓
Frontend updates chat list UI for all connected members
```

## Testing

### Test Real-Time Updates
1. Open chat list in two different browsers (User A & User B)
2. Send message from User A to User B
3. **Expected**: User B's chat list updates immediately
4. **Expected**: Unread badge appears for User B

### Test Group Updates
1. Open chat list for 3 group members
2. Send message in group from one member
3. **Expected**: All members see chat list update instantly
4. **Expected**: Sender sees 0 unread, others see 1 unread

### Test Reconnection
1. Open chat list
2. Stop/restart web container
3. **Expected**: WebSocket reconnects automatically within 3-5 seconds
4. **Expected**: Chat list continues to receive updates

## Security

### Authentication
- Only authenticated users can connect
- Each user has private channel: `chat_list_{user_id}`
- Cannot receive other users' chat lists

### Authorization
- Thread participants validated before data sent
- Group members validated before data sent
- Unread counts are personalized per user

### Data Privacy
- Messages are encrypted in database
- WebSocket only sends last message preview (plaintext)
- Profile pictures respect user privacy settings

## Performance

### Optimizations
- Lazy loading with `select_related()` for foreign keys
- Efficient unread count queries using database annotations
- Single query per chat list update
- Debounced reconnection attempts

### Scalability
- Each user has separate channel group
- No broadcast storms (only affected users notified)
- Celery workers handle database queries asynchronously
- Redis channels layer handles WebSocket routing

## Troubleshooting

### WebSocket Not Connecting
1. Check browser console for errors
2. Verify Redis is running: `docker compose ps redis`
3. Check web server logs: `docker compose logs -f web`
4. Ensure `CHANNEL_LAYERS` configured in settings

### Updates Not Appearing
1. Verify WebSocket connected (check console logs)
2. Check if user is participant/member
3. Verify message was saved successfully
4. Check worker logs: `docker compose logs -f worker`

### Incorrect Unread Counts
1. Verify `read_at` field set when messages read
2. Check `read_by` ManyToMany for group messages
3. Ensure mark_messages_as_read() called on connect
4. Review unread count query logic in helpers

## Future Enhancements

- [ ] Typing indicators in chat list
- [ ] Online/offline status indicators
- [ ] Message preview shows sender name in groups
- [ ] Push notifications for background tabs
- [ ] Service worker for offline support
- [ ] Read receipts in chat list
