from django.contrib import admin
from .models import Investment, InvestmentTransaction, InvestmentDocument


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'investment_type', 'amount_invested', 'current_value', 'status', 'date_invested']
    list_filter = ['investment_type', 'status']
    search_fields = ['name', 'location']


@admin.register(InvestmentTransaction)
class InvestmentTransactionAdmin(admin.ModelAdmin):
    list_display = ['investment', 'tx_type', 'amount', 'date']
    list_filter = ['tx_type']


admin.site.register(InvestmentDocument)
