from django.contrib import admin

# Register your models here.

# end_call/admin.py
from django.contrib import admin
from .models import UserAPIKey, ChatSession, ChatMessage

class UserAPIKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'service_name', 'created_at', 'updated_at')
    list_filter = ('service_name', 'user')
    search_fields = ('user__username', 'service_name')
    # IMPORTANT: Exclude the raw encrypted field from direct display/edit in admin
    # Add custom methods or forms if admin needs to manage keys (with extreme care)
    readonly_fields = ('encrypted_api_key',) # Make it readonly for safety

    # If you need to SET keys via admin (use with caution):
    # You would need a custom form that takes the raw key and calls set_api_key

admin.site.register(UserAPIKey, UserAPIKeyAdmin)


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0 # Don't show extra empty forms
    readonly_fields = ('role', 'content', 'timestamp') # Usually read-only context
    ordering = ('timestamp',)


class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'ai_model_identifier', 'created_at', 'updated_at')
    list_filter = ('user', 'ai_model_identifier', 'created_at')
    search_fields = ('title', 'user__username', 'id')
    inlines = [ChatMessageInline]
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(ChatSession, ChatSessionAdmin)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_id_link', 'role', 'content_preview', 'timestamp')
    list_filter = ('role', 'timestamp', 'session__user', 'session__ai_model_identifier')
    search_fields = ('content', 'session__id', 'session__user__username')
    readonly_fields = ('timestamp',)
    list_select_related = ('session', 'session__user') # Optimize query

    def session_id_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        session_admin_url = reverse('admin:end_call_chatsession_change', args=[obj.session.pk])
        return format_html('<a href="{}">{}</a>', session_admin_url, obj.session.pk)
    session_id_link.short_description = 'Session ID'
    session_id_link.admin_order_field = 'session__id' # Allow sorting by session ID

    def content_preview(self, obj):
        return (obj.content[:50] + '...') if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'