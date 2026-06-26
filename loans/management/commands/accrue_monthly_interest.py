"""
Management command: recalculate total_payable for all active monthly_interest loans.
Run daily via cron: python manage.py accrue_monthly_interest
"""
from django.core.management.base import BaseCommand
from loans.models import Loan


class Command(BaseCommand):
    help = 'Recalculate accrued interest for monthly-interest loans'

    def handle(self, *args, **options):
        loans = Loan.objects.filter(
            product__interest_method='monthly_interest',
            status__in=['active', 'late'],
        ).select_related('product')

        updated = 0
        for loan in loans:
            if loan.recalculate_monthly_interest():
                updated += 1
                self.stdout.write(
                    f"  Updated Loan #{loan.pk} ({loan.member}) — "
                    f"new total: KES {loan.total_payable:,.2f}"
                )

        self.stdout.write(self.style.SUCCESS(
            f"Done. {updated} loan(s) updated out of {loans.count()} checked."
        ))
