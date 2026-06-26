from django.core.management.base import BaseCommand
from django.utils import timezone
from loans.models import Loan


class Command(BaseCommand):
    help = 'Mark overdue loans as late'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        marked = Loan.objects.filter(status='active', due_date__lt=today).update(status='late')
        self.stdout.write(self.style.SUCCESS(f'{marked} loan(s) marked as late.'))
