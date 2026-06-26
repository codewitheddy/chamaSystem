from django.contrib import admin
from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['member', 'event', 'channel', 'status', 'created_at']
    list_filter = ['channel', 'event', 'status']
    search_fields = ['member__name', 'subject', 'message']
    readonly_fields = ['created_at', 'sent_at', 'error_detail']


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['member', 'email_enabled', 'sms_enabled', 'whatsapp_enabled']
    search_fields = ['member__name']
