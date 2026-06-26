from django.contrib import admin
from .models import WelfareClaim, WelfareContribution, WelfareSettings


@admin.register(WelfareClaim)
class WelfareClaimAdmin(admin.ModelAdmin):
    list_display = ['pk', 'member', 'claim_type', 'amount_requested', 'amount_disbursed', 'status', 'date_filed']
    list_filter = ['status', 'claim_type']
    search_fields = ['member__name', 'beneficiary_name']


@admin.register(WelfareContribution)
class WelfareContributionAdmin(admin.ModelAdmin):
    list_display = ['member', 'amount', 'date', 'payment_method', 'claim', 'is_voided']
    list_filter = ['payment_method', 'is_voided']
    search_fields = ['member__name']


@admin.register(WelfareSettings)
class WelfareSettingsAdmin(admin.ModelAdmin):
    list_display = ['standard_contribution', 'is_active', 'updated_at']
