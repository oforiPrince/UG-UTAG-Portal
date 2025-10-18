from django.contrib import admin

from .models import ChatGroup, ChatThread, GroupMembership, GroupMessage, Message


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_one', 'user_two', 'last_message_at')
    search_fields = ('user_one__email', 'user_two__email', 'user_one__surname', 'user_two__surname')
    readonly_fields = ('created_at', 'updated_at', 'last_message_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'thread', 'sender', 'created_at', 'read_at')
    list_filter = ('created_at', 'read_at')
    search_fields = ('sender__email', 'thread__user_one__email', 'thread__user_two__email')
    readonly_fields = ('created_at', 'ciphertext')


@admin.register(ChatGroup)
class ChatGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_by', 'created_at')
    search_fields = ('name', 'created_by__email')
    readonly_fields = ('created_at', 'updated_at', 'encryption_key')


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'user', 'added_by', 'added_at')
    search_fields = ('group__name', 'user__email')
    readonly_fields = ('added_at',)


@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'sender', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('group__name', 'sender__email')
    readonly_fields = ('created_at', 'ciphertext')
