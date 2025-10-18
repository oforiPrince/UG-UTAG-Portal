from django.urls import path

from .consumers import GroupChatConsumer, ThreadChatConsumer

websocket_urlpatterns = [
    path('ws/chat/thread/<int:thread_id>/', ThreadChatConsumer.as_asgi(), name='thread_chat_ws'),
    path('ws/chat/group/<int:group_id>/', GroupChatConsumer.as_asgi(), name='group_chat_ws'),
]
