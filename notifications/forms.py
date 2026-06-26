from django import forms
from .models import NotificationPreference, Notification


class BroadcastForm(forms.Form):
    subject = forms.CharField(max_length=255)
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}))
    send_email = forms.BooleanField(required=False, initial=True, label='Email')
    send_sms = forms.BooleanField(required=False, initial=True, label='SMS')
    send_whatsapp = forms.BooleanField(required=False, label='WhatsApp')


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = ['email_enabled', 'sms_enabled', 'whatsapp_enabled']
        labels = {
            'email_enabled': 'Email notifications',
            'sms_enabled': 'SMS notifications',
            'whatsapp_enabled': 'WhatsApp notifications',
        }
