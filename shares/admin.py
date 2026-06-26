from django.contrib import admin
from .models import ShareConfig, ShareAccount, ShareTransaction


@admin.register(ShareConfig)
class ShareConfigAdmin(admin.ModelAdmin):
    list_display = ['par_value', 'min_shares', 'max_shares', 'loan_multiplier']


class ShareTransactionInline(admin.TabularInline):
    model = ShareTransaction
    extra = 0
    readonly_fields = ['created_at', 'created_by']


@admin.register(ShareAccount)
class ShareAccountAdmin(admin.ModelAdmin):
    list_display = ['member', 'shares_held', 'share_value', 'updated_at']
    inlines = [ShareTransactionInline]
    readonly_fields = ['shares_held', 'created_at', 'updated_at']


@admin.register(ShareTransaction)
class ShareTransactionAdmin(admin.ModelAdmin):
    list_display = ['account', 'transaction_type', 'shares', 'amount', 'date', 'created_by']
    list_filter = ['transaction_type', 'date']
