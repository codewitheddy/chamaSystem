from django.core.management.base import BaseCommand
from django.utils import timezone
from contributions.models import Contribution
from members.models import Member
import calendar


class Command(BaseCommand):
    help = 'Print active members who have not yet contributed this month'

    def add_arguments(self, parser):
        parser.add_argument('--month', type=int, help='Month number (default: current month)')
        parser.add_argument('--year', type=int, help='Year (default: current year)')

    def handle(self, *args, **options):
        today = timezone.now().date()
        month = options.get('month') or today.month
        year = options.get('year') or today.year
        month_name = calendar.month_name[month]

        paid_ids = Contribution.objects.filter(
            month=month, year=year, is_voided=False
        ).values_list('member_id', flat=True)

        defaulters = Member.objects.filter(status='active').exclude(id__in=paid_ids)
        for member in defaulters:
            self.stdout.write(f'  - {member.name} ({member.phone})')

        self.stdout.write(self.style.SUCCESS(
            f'{defaulters.count()} defaulter(s) for {month_name} {year}.'
        ))
