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
    remove_group_member,
    toggle_group_admin,
    create_group_invite,
    accept_group_invite,
    delete_message,
)
from .group_api import (
    get_available_members,
    add_members_to_group,
    remove_member_from_group,
    promote_group_member,
    update_group_info,
    leave_group,
    join_group_via_link,
)

app_name = 'chat'

urlpatterns = [
    # Main chat list (unified direct + groups)
    path('', ThreadListView.as_view(), name='thread_list'),
    
    # Start new chat
    path('start/', ThreadStartView.as_view(), name='thread_start'),
    
    # Unified conversation view (handles both direct and group chats)
    path('thread/<str:pk>/', UnifiedConversationView.as_view(), 
         {'chat_type': 'direct'}, name='thread_detail'),
    path('group/<str:pk>/', UnifiedConversationView.as_view(), 
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
    # Group admin endpoints
    path('api/group/<int:group_id>/remove-member/', remove_group_member, name='remove_group_member'),
    path('api/group/<int:group_id>/toggle-admin/', toggle_group_admin, name='toggle_group_admin'),
    path('api/group/<int:group_id>/create-invite/', create_group_invite, name='create_group_invite'),
    path('api/group/invite/<str:token>/', accept_group_invite, name='accept_group_invite'),
    path('api/message/delete/', delete_message, name='delete_message'),
    
    # Group management endpoints (new)
    path('group/<int:group_id>/available-members/', get_available_members, name='get_available_members'),
    path('group/<int:group_id>/add-members/', add_members_to_group, name='add_members_to_group'),
    path('group/<int:group_id>/member/<int:member_id>/remove/', remove_member_from_group, name='remove_member_from_group'),
    path('group/<int:group_id>/member/<int:member_id>/promote/', promote_group_member, name='promote_group_member'),
    path('group/<int:group_id>/update/', update_group_info, name='update_group_info'),
    path('group/<int:group_id>/leave/', leave_group, name='leave_group'),
    path('group/join/<str:token>/', join_group_via_link, name='join_group_via_link'),
]
