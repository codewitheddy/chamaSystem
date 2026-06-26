"""
Backfill double-entry journal entries for all existing records.

Run once after installing the ledger app:
    python manage.py backfill_ledger

Safe to re-run — uses get_or_create logic via source_app + source_id.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal


class Command(BaseCommand):
    help = 'Backfill ledger journal entries from existing financial records'

    def handle(self, *args, **options):
        from ledger.signals import _post, _get_chama, _delete_entry
        from ledger.coa import seed_chart_of_accounts
        from ledger.models import JournalEntry
        from tenants.models import Chama

        # Ensure all chamas have a CoA
        for chama in Chama.objects.all():
            seed_chart_of_accounts(chama)
        self.stdout.write(f"CoA seeded for {Chama.objects.count()} chama(s).")

        totals = {}

        with transaction.atomic():

            # ── Contributions ────────────────────────────────────────────────
            from contributions.models import Contribution
            count = 0
            for c in Contribution.objects.select_related('member__chama').filter(is_voided=False):
                chama = _get_chama(c.member)
                if not chama:
                    continue
                # Skip if already exists
                if JournalEntry.objects.filter(source_app='contribution', source_id=c.pk, chama=chama).exists():
                    continue
                _post(chama, c.date,
                      f"Contribution — {c.member.name} ({c.get_month_display()} {c.year})",
                      f"CONT-{c.pk}", 'contribution', c.pk,
                      [('1000', 'debit',  c.amount, 'Cash received', c.member),
                       ('4000', 'credit', c.amount, 'Contribution income', c.member)])
                count += 1
            totals['contributions'] = count
            self.stdout.write(f"  Contributions: {count}")

            # ── Loans ────────────────────────────────────────────────────────
            from loans.models import Loan
            count = 0
            for l in Loan.objects.select_related('member__chama'):
                chama = _get_chama(l.member)
                if not chama:
                    continue
                if JournalEntry.objects.filter(source_app='loan', source_id=l.pk, chama=chama).exists():
                    continue
                _post(chama, l.date_taken,
                      f"Loan disbursed — {l.member.name}",
                      f"LOAN-{l.pk}", 'loan', l.pk,
                      [('1100', 'debit',  l.loan_amount, 'Loan receivable', l.member),
                       ('1000', 'credit', l.loan_amount, 'Cash paid out',   l.member)])
                count += 1
            totals['loans'] = count
            self.stdout.write(f"  Loans: {count}")

            # ── Payments ─────────────────────────────────────────────────────
            from payments.models import Payment
            count = 0
            for p in Payment.objects.select_related('member__chama', 'loan').filter(is_voided=False):
                chama = _get_chama(p.member)
                if not chama:
                    continue
                if JournalEntry.objects.filter(source_app='payment', source_id=p.pk, chama=chama).exists():
                    continue
                loan = p.loan
                if loan.total_payable > 0 and loan.interest_amount > 0:
                    interest_ratio = loan.interest_amount / loan.total_payable
                    interest = (p.amount * interest_ratio).quantize(Decimal('0.01'))
                    principal = p.amount - interest
                else:
                    principal = p.amount
                    interest = Decimal('0.00')
                lines = [
                    ('1000', 'debit',  p.amount,   'Cash received',  p.member),
                    ('1100', 'credit', principal,   'Loan repayment', p.member),
                ]
                if interest > 0:
                    lines.append(('4100', 'credit', interest, 'Interest income', p.member))
                _post(chama, p.date,
                      f"Loan repayment — {p.member.name} (Loan #{loan.pk})",
                      f"PAY-{p.pk}", 'payment', p.pk, lines)
                count += 1
            totals['payments'] = count
            self.stdout.write(f"  Payments: {count}")

            # ── Penalties ────────────────────────────────────────────────────
            from meetings.models import MeetingPenalty
            count = 0
            for pen in MeetingPenalty.objects.select_related('member__chama', 'meeting').filter(paid=True, is_voided=False):
                chama = _get_chama(pen.member)
                if not chama:
                    continue
                if JournalEntry.objects.filter(source_app='penalty', source_id=pen.pk, chama=chama).exists():
                    continue
                amount = pen.amount_paid or pen.amount
                _post(chama, pen.meeting.date,
                      f"Penalty — {pen.member.name} ({pen.get_reason_display()})",
                      f"PEN-{pen.pk}", 'penalty', pen.pk,
                      [('1000', 'debit',  amount, 'Cash received',  pen.member),
                       ('4200', 'credit', amount, 'Penalty income', pen.member)])
                count += 1
            totals['penalties'] = count
            self.stdout.write(f"  Penalties: {count}")

            # ── Expenses ─────────────────────────────────────────────────────
            from accounting.models import Expense
            count = 0
            for e in Expense.objects.filter(is_voided=False):
                chama = getattr(e, 'chama', None)
                if not chama:
                    continue
                if JournalEntry.objects.filter(source_app='expense', source_id=e.pk, chama=chama).exists():
                    continue
                _post(chama, e.date,
                      e.description, f"EXP-{e.pk}", 'expense', e.pk,
                      [('5000', 'debit',  e.amount, e.description, None),
                       ('1000', 'credit', e.amount, 'Cash paid out', None)])
                count += 1
            totals['expenses'] = count
            self.stdout.write(f"  Expenses: {count}")

            # ── Share transactions ────────────────────────────────────────────
            from shares.models import ShareTransaction, ShareTransaction as ST
            count = 0
            for st in ShareTransaction.objects.select_related('account__member__chama'):
                chama = _get_chama(st.account.member)
                if not chama:
                    continue
                if JournalEntry.objects.filter(source_app='share', source_id=st.pk, chama=chama).exists():
                    continue
                if st.transaction_type == ST.TYPE_PURCHASE:
                    _post(chama, st.date,
                          f"Share purchase — {st.account.member.name}",
                          f"SHR-{st.pk}", 'share', st.pk,
                          [('1000', 'debit',  st.amount, 'Cash received', st.account.member),
                           ('3000', 'credit', st.amount, 'Share capital',  st.account.member)])
                    count += 1
                elif st.transaction_type == ST.TYPE_REFUND:
                    _post(chama, st.date,
                          f"Share refund — {st.account.member.name}",
                          f"SHR-{st.pk}", 'share', st.pk,
                          [('3000', 'debit',  st.amount, 'Share capital', st.account.member),
                           ('1000', 'credit', st.amount, 'Cash paid out', st.account.member)])
                    count += 1
            totals['shares'] = count
            self.stdout.write(f"  Share transactions: {count}")

            # ── Welfare contributions ─────────────────────────────────────────
            from welfare.models import WelfareContribution, WelfareClaim
            count = 0
            for wc in WelfareContribution.objects.select_related('member__chama').filter(is_voided=False):
                chama = _get_chama(wc.member)
                if not chama:
                    continue
                if JournalEntry.objects.filter(source_app='welfare_contrib', source_id=wc.pk, chama=chama).exists():
                    continue
                _post(chama, wc.date,
                      f"Welfare contribution — {wc.member.name}",
                      f"WFC-{wc.pk}", 'welfare_contrib', wc.pk,
                      [('1400', 'debit',  wc.amount, 'Welfare fund cash',    wc.member),
                       ('2000', 'credit', wc.amount, 'Welfare fund payable', wc.member)])
                count += 1
            totals['welfare_contribs'] = count
            self.stdout.write(f"  Welfare contributions: {count}")

            # ── Welfare disbursements ─────────────────────────────────────────
            count = 0
            for wf in WelfareClaim.objects.select_related('member__chama').filter(status='disbursed'):
                chama = _get_chama(wf.member)
                if not chama or not wf.amount_disbursed:
                    continue
                if JournalEntry.objects.filter(source_app='welfare_claim', source_id=wf.pk, chama=chama).exists():
                    continue
                _post(chama, wf.date_disbursed or wf.date_filed,
                      f"Welfare disbursement — {wf.beneficiary} ({wf.get_claim_type_display()})",
                      f"WFD-{wf.pk}", 'welfare_claim', wf.pk,
                      [('5100', 'debit',  wf.amount_disbursed, 'Welfare disbursement', wf.member),
                       ('1400', 'credit', wf.amount_disbursed, 'Welfare fund cash',    wf.member)])
                count += 1
            totals['welfare_claims'] = count
            self.stdout.write(f"  Welfare disbursements: {count}")

            # ── Registration fees ─────────────────────────────────────────────
            from members.models import Member
            from datetime import date as _date
            count = 0
            for m in Member.objects.select_related('chama').filter(registration_fee__gt=0):
                chama = getattr(m, 'chama', None)
                if not chama:
                    continue
                if JournalEntry.objects.filter(source_app='registration', source_id=m.pk, chama=chama).exists():
                    continue
                _post(chama, m.date_joined or _date.today(),
                      f"Registration fee — {m.name}",
                      f"REG-{m.pk}", 'registration', m.pk,
                      [('1000', 'debit',  m.registration_fee, 'Cash received',       m),
                       ('4300', 'credit', m.registration_fee, 'Registration income', m)])
                count += 1
            totals['registrations'] = count
            self.stdout.write(f"  Registration fees: {count}")

            # ── Other income ──────────────────────────────────────────────────
            from accounting.models import OtherIncome
            count = 0
            for oi in OtherIncome.objects.filter(is_voided=False):
                chama = getattr(oi, 'chama', None)
                if not chama:
                    continue
                if JournalEntry.objects.filter(source_app='other_income', source_id=oi.pk, chama=chama).exists():
                    continue
                _post(chama, oi.date,
                      f"{oi.get_source_display()} — {oi.description}",
                      f"OTH-{oi.pk}", 'other_income', oi.pk,
                      [('1000', 'debit',  oi.amount, 'Cash received', None),
                       ('4500', 'credit', oi.amount, 'Other income',  None)])
                count += 1
            totals['other_income'] = count
            self.stdout.write(f"  Other income: {count}")

            # ── Member exit settlements ───────────────────────────────────────
            count = 0
            for m in Member.objects.select_related('chama').filter(
                    status='exited', exit_settlement_amount__isnull=False):
                chama = getattr(m, 'chama', None)
                if not chama or not m.exit_settlement_amount:
                    continue
                if JournalEntry.objects.filter(source_app='exit', source_id=m.pk, chama=chama).exists():
                    continue
                amount = abs(m.exit_settlement_amount)
                exit_date = m.exit_date or _date.today()
                if m.exit_settlement_amount > 0:
                    _post(chama, exit_date,
                          f"Member exit refund — {m.name}",
                          f"EXIT-{m.pk}", 'exit', m.pk,
                          [('3100', 'debit',  amount, 'Member exit — equity reduction', m),
                           ('1000', 'credit', amount, 'Cash paid out',                  m)])
                else:
                    _post(chama, exit_date,
                          f"Member exit debt collected — {m.name}",
                          f"EXIT-{m.pk}", 'exit', m.pk,
                          [('1000', 'debit',  amount, 'Cash received',                  m),
                           ('3100', 'credit', amount, 'Member exit — equity recovery',  m)])
                count += 1
            totals['exits'] = count
            self.stdout.write(f"  Member exit settlements: {count}")

        total_entries = sum(totals.values())
        self.stdout.write(self.style.SUCCESS(
            f"\nBackfill complete. {total_entries} journal entries created."
        ))
