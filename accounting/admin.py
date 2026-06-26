from django.contrib import admin
from .models import Transaction, Expense


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['date', 'category', 'direction', 'amount', 'description', 'member', 'is_manual']
    list_filter = ['category', 'direction', 'is_manual']
    search_fields = ['description', 'reference', 'member__name']
    date_hierarchy = 'date'
    readonly_fields = ['created_at']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['date', 'description', 'amount', 'category', 'receipt_no']
    list_filter = ['category']
    search_fields = ['description', 'receipt_no']
    date_hierarchy = 'date'
