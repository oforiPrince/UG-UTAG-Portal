from django.urls import path

from .views import (
    GroupCreateView,
    ThreadListView,
    ThreadStartView,
    UnifiedConversationView,
)
from .api import (
    get_users_list,
    start_direct_chat,
    create_group_ajax,
    mark_thread_read,
    mark_group_read,
    download_message_attachment,
    download_group_message_attachment,
    download_message_attachment_thumbnail,
    download_group_message_attachment_thumbnail,
)

app_name = 'chat'

urlpatterns = [
    # Main chat list (unified direct + groups)
    path('', ThreadListView.as_view(), name='thread_list'),
    
    # Start new chat
    path('start/', ThreadStartView.as_view(), name='thread_start'),
    
    # Unified conversation view (handles both direct and group chats)
    path('thread/<int:pk>/', UnifiedConversationView.as_view(), 
         {'chat_type': 'direct'}, name='thread_detail'),
    path('group/<int:pk>/', UnifiedConversationView.as_view(), 
         {'chat_type': 'group'}, name='group_detail'),
    
    # Group management
    path('groups/create/', GroupCreateView.as_view(), name='group_create'),
    
    # API endpoints for simple modal interface
    path('api/users/', get_users_list, name='get_users_list'),
    path('api/start-chat/', start_direct_chat, name='start_direct_chat'),
    path('api/create-group/', create_group_ajax, name='create_group_ajax'),
    path('api/mark-thread-read/<int:thread_id>/', mark_thread_read, name='mark_thread_read'),
    path('api/mark-group-read/<int:group_id>/', mark_group_read, name='mark_group_read'),
    path('api/attachment/<int:attachment_id>/',
        download_message_attachment, name='download_message_attachment'),
    path('api/group-attachment/<int:attachment_id>/',
        download_group_message_attachment, name='download_group_message_attachment'),
    path('api/attachment/<int:attachment_id>/thumb/',
        download_message_attachment_thumbnail, name='download_message_attachment_thumbnail'),
    path('api/group-attachment/<int:attachment_id>/thumb/',
        download_group_message_attachment_thumbnail, name='download_group_message_attachment_thumbnail'),
]
