from django.contrib import admin
from .models import Loan


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ['member', 'loan_amount', 'duration_months', 'interest_amount',
                    'total_payable', 'amount_paid', 'status', 'date_taken', 'due_date']
    list_filter = ['status']
    search_fields = ['member__name']
    readonly_fields = ['interest_amount', 'total_payable']
