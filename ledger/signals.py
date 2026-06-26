"""
Auto-post double-entry journal entries from existing app events.

Mapping:
  Contribution recorded  → DR Cash(1000)  CR Contribution Income(4000)
  Loan disbursed         → DR Loans Receivable(1100)  CR Cash(1000)
  Loan repayment         → DR Cash(1000)  CR Loans Receivable(1100)
                           DR Cash(1000)  CR Interest Income(4100)  [interest portion]
  Penalty collected      → DR Cash(1000)  CR Penalty Income(4200)
  Expense recorded       → DR Operating Expenses(5000)  CR Cash(1000)
  Share purchase         → DR Cash(1000)  CR Member Share Capital(3000)
  Welfare contribution   → DR Welfare Fund Cash(1400)  CR Welfare Fund Payable(2000)
  Welfare disbursement   → DR Welfare Fund Payable(2000)  CR Welfare Fund Cash(1400)
  Investment capital     → DR Investments(1300)  CR Cash(1000)
  Investment income      → DR Cash(1000)  CR Investment Income(4400)
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal


def _post(chama, date, description, reference, source_app, source_id, lines):
    """
    Create a balanced JournalEntry.
    lines = list of (account_code, side, amount, memo, member)
    """
    if not chama:
        return
    from .models import JournalEntry, JournalLine
    from .coa import get_account

    entry = JournalEntry.objects.create(
        chama=chama,
        date=date,
        description=description,
        reference=reference,
        source_app=source_app,
        source_id=source_id,
        is_posted=True,
    )
    for code, side, amount, memo, member in lines:
        acct = get_account(chama, code)
        if acct and amount and amount > 0:
            JournalLine.objects.create(
                entry=entry,
                account=acct,
                side=side,
                amount=amount,
                memo=memo or '',
                member=member,
            )
    return entry


def _delete_entry(source_app, source_id, chama):
    from .models import JournalEntry
    JournalEntry.objects.filter(
        source_app=source_app, source_id=source_id, chama=chama
    ).delete()


def _get_chama(member):
    return getattr(member, 'chama', None)


# ── Contributions ────────────────────────────────────────────────────────────

@receiver(post_save, sender='contributions.Contribution')
def on_contribution(sender, instance, created, **kwargs):
    chama = _get_chama(instance.member)
    _delete_entry('contribution', instance.pk, chama)
    if instance.is_voided or not chama:
        return
    _post(chama, instance.date,
          f"Contribution — {instance.member.name} ({instance.get_month_display()} {instance.year})",
          f"CONT-{instance.pk}",
          'contribution', instance.pk,
          [
              ('1000', 'debit',  instance.amount, 'Cash received', instance.member),
              ('4000', 'credit', instance.amount, 'Contribution income', instance.member),
          ])


@receiver(post_delete, sender='contributions.Contribution')
def on_contribution_delete(sender, instance, **kwargs):
    _delete_entry('contribution', instance.pk, _get_chama(instance.member))


# ── Loans ────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='loans.Loan')
def on_loan(sender, instance, created, **kwargs):
    if not created:
        return
    chama = _get_chama(instance.member)
    if not chama:
        return
    _post(chama, instance.date_taken,
          f"Loan disbursed — {instance.member.name}",
          f"LOAN-{instance.pk}",
          'loan', instance.pk,
          [
              ('1100', 'debit',  instance.loan_amount, 'Loan receivable', instance.member),
              ('1000', 'credit', instance.loan_amount, 'Cash paid out',   instance.member),
          ])


@receiver(post_delete, sender='loans.Loan')
def on_loan_delete(sender, instance, **kwargs):
    _delete_entry('loan', instance.pk, _get_chama(instance.member))


# ── Payments (loan repayments) ───────────────────────────────────────────────

@receiver(post_save, sender='payments.Payment')
def on_payment(sender, instance, created, **kwargs):
    chama = _get_chama(instance.member)
    _delete_entry('payment', instance.pk, chama)
    if instance.is_voided or not chama:
        return
    loan = instance.loan
    # Split into principal + interest
    if loan.total_payable > 0 and loan.interest_amount > 0:
        interest_ratio = loan.interest_amount / loan.total_payable
        interest = (instance.amount * interest_ratio).quantize(Decimal('0.01'))
        principal = instance.amount - interest
    else:
        principal = instance.amount
        interest = Decimal('0.00')

    lines = [
        ('1000', 'debit',  instance.amount, 'Cash received', instance.member),
        ('1100', 'credit', principal,        'Loan repayment', instance.member),
    ]
    if interest > 0:
        lines.append(('4100', 'credit', interest, 'Interest income', instance.member))

    _post(chama, instance.date,
          f"Loan repayment — {instance.member.name} (Loan #{loan.pk})",
          f"PAY-{instance.pk}",
          'payment', instance.pk, lines)


@receiver(post_delete, sender='payments.Payment')
def on_payment_delete(sender, instance, **kwargs):
    _delete_entry('payment', instance.pk, _get_chama(instance.member))


# ── Penalties ────────────────────────────────────────────────────────────────

@receiver(post_save, sender='meetings.MeetingPenalty')
def on_penalty(sender, instance, **kwargs):
    chama = _get_chama(instance.member)
    _delete_entry('penalty', instance.pk, chama)
    if instance.is_voided or not instance.paid or not chama:
        return
    amount = instance.amount_paid or instance.amount
    _post(chama, instance.meeting.date,
          f"Penalty — {instance.member.name} ({instance.get_reason_display()})",
          f"PEN-{instance.pk}",
          'penalty', instance.pk,
          [
              ('1000', 'debit',  amount, 'Cash received', instance.member),
              ('4200', 'credit', amount, 'Penalty income', instance.member),
          ])


@receiver(post_delete, sender='meetings.MeetingPenalty')
def on_penalty_delete(sender, instance, **kwargs):
    _delete_entry('penalty', instance.pk, _get_chama(instance.member))


# ── Expenses ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='accounting.Expense')
def on_expense(sender, instance, **kwargs):
    chama = getattr(instance, 'chama', None)
    _delete_entry('expense', instance.pk, chama)
    if instance.is_voided or not chama:
        return
    _post(chama, instance.date,
          instance.description,
          f"EXP-{instance.pk}",
          'expense', instance.pk,
          [
              ('5000', 'debit',  instance.amount, instance.description, None),
              ('1000', 'credit', instance.amount, 'Cash paid out',      None),
          ])


@receiver(post_delete, sender='accounting.Expense')
def on_expense_delete(sender, instance, **kwargs):
    _delete_entry('expense', instance.pk, getattr(instance, 'chama', None))


# ── Share purchases ───────────────────────────────────────────────────────────

@receiver(post_save, sender='shares.ShareTransaction')
def on_share_tx(sender, instance, created, **kwargs):
    if not created:
        return
    chama = _get_chama(instance.account.member)
    if not chama:
        return
    from shares.models import ShareTransaction as ST
    if instance.transaction_type == ST.TYPE_PURCHASE:
        _post(chama, instance.date,
              f"Share purchase — {instance.account.member.name}",
              f"SHR-{instance.pk}",
              'share', instance.pk,
              [
                  ('1000', 'debit',  instance.amount, 'Cash received',      instance.account.member),
                  ('3000', 'credit', instance.amount, 'Share capital',       instance.account.member),
              ])
    elif instance.transaction_type == ST.TYPE_REFUND:
        _post(chama, instance.date,
              f"Share refund — {instance.account.member.name}",
              f"SHR-{instance.pk}",
              'share', instance.pk,
              [
                  ('3000', 'debit',  instance.amount, 'Share capital',  instance.account.member),
                  ('1000', 'credit', instance.amount, 'Cash paid out',  instance.account.member),
              ])


# ── Welfare contributions ─────────────────────────────────────────────────────

@receiver(post_save, sender='welfare.WelfareContribution')
def on_welfare_contrib(sender, instance, **kwargs):
    chama = _get_chama(instance.member)
    _delete_entry('welfare_contrib', instance.pk, chama)
    if instance.is_voided or not chama:
        return
    _post(chama, instance.date,
          f"Welfare contribution — {instance.member.name}",
          f"WFC-{instance.pk}",
          'welfare_contrib', instance.pk,
          [
              ('1400', 'debit',  instance.amount, 'Welfare fund cash',    instance.member),
              ('2000', 'credit', instance.amount, 'Welfare fund payable', instance.member),
          ])


@receiver(post_delete, sender='welfare.WelfareContribution')
def on_welfare_contrib_delete(sender, instance, **kwargs):
    _delete_entry('welfare_contrib', instance.pk, _get_chama(instance.member))


# ── Welfare disbursements ─────────────────────────────────────────────────────

@receiver(post_save, sender='welfare.WelfareClaim')
def on_welfare_claim(sender, instance, **kwargs):
    chama = _get_chama(instance.member)
    _delete_entry('welfare_claim', instance.pk, chama)
    if instance.status != 'disbursed' or not instance.amount_disbursed or not chama:
        return
    _post(chama, instance.date_disbursed or instance.date_filed,
          f"Welfare disbursement — {instance.beneficiary} ({instance.get_claim_type_display()})",
          f"WFD-{instance.pk}",
          'welfare_claim', instance.pk,
          [
              ('5100', 'debit',  instance.amount_disbursed, 'Welfare disbursement', instance.member),
              ('1400', 'credit', instance.amount_disbursed, 'Welfare fund cash',    instance.member),
          ])


# ── Investment capital ────────────────────────────────────────────────────────

@receiver(post_save, sender='investments.InvestmentTransaction')
def on_investment_tx(sender, instance, created, **kwargs):
    if not created:
        return
    chama = getattr(instance.investment, 'chama', None)
    if not chama:
        return
    from investments.models import InvestmentTransaction as IT
    if instance.tx_type == IT.TYPE_INJECTION:
        _post(chama, instance.date,
              f"Investment — {instance.investment.name}",
              f"INV-{instance.pk}",
              'investment', instance.pk,
              [
                  ('1300', 'debit',  instance.amount, 'Investment asset', None),
                  ('1000', 'credit', instance.amount, 'Cash paid out',    None),
              ])
    elif instance.tx_type in (IT.TYPE_INCOME, IT.TYPE_DIVIDEND, IT.TYPE_EXIT):
        _post(chama, instance.date,
              f"Investment income — {instance.investment.name}",
              f"INV-{instance.pk}",
              'investment', instance.pk,
              [
                  ('1000', 'debit',  instance.amount, 'Cash received',    None),
                  ('4400', 'credit', instance.amount, 'Investment income', None),
              ])


# ── Registration fees ─────────────────────────────────────────────────────────

@receiver(post_save, sender='members.Member')
def on_member_registration(sender, instance, created, **kwargs):
    """Post registration fee to ledger when a new member is added with a non-zero fee."""
    if not created:
        return
    chama = getattr(instance, 'chama', None)
    if not chama or not instance.registration_fee or instance.registration_fee <= 0:
        return
    from datetime import date as _date
    _post(chama, instance.date_joined or _date.today(),
          f"Registration fee — {instance.name}",
          f"REG-{instance.pk}",
          'registration', instance.pk,
          [
              ('1000', 'debit',  instance.registration_fee, 'Cash received',       instance),
              ('4300', 'credit', instance.registration_fee, 'Registration income', instance),
          ])


# ── Member exit settlement ────────────────────────────────────────────────────

@receiver(post_save, sender='members.Member')
def on_member_exit(sender, instance, created, **kwargs):
    """
    Post exit settlement when a member exits with a settlement amount.
    Refund (net positive) → DR Member Contributions Equity / CR Cash
    Debt collection (net negative) → DR Cash / CR Member Contributions Equity
    """
    if created:
        return
    if instance.status != 'exited' or not instance.exit_settlement_amount:
        return
    chama = getattr(instance, 'chama', None)
    if not chama:
        return

    # Only post once — check if already exists
    from ledger.models import JournalEntry
    if JournalEntry.objects.filter(source_app='exit', source_id=instance.pk, chama=chama).exists():
        return

    amount = abs(instance.exit_settlement_amount)
    from datetime import date as _date
    exit_date = instance.exit_date or _date.today()

    if instance.exit_settlement_amount > 0:
        # Refund paid out to member
        _post(chama, exit_date,
              f"Member exit refund — {instance.name}",
              f"EXIT-{instance.pk}",
              'exit', instance.pk,
              [
                  ('3100', 'debit',  amount, 'Member exit — equity reduction', instance),
                  ('1000', 'credit', amount, 'Cash paid out',                  instance),
              ])
    else:
        # Member owed money — collected from them
        _post(chama, exit_date,
              f"Member exit debt collected — {instance.name}",
              f"EXIT-{instance.pk}",
              'exit', instance.pk,
              [
                  ('1000', 'debit',  amount, 'Cash received',                  instance),
                  ('3100', 'credit', amount, 'Member exit — equity recovery',  instance),
              ])


# ── Other Income (bank interest, dividends, grants) ───────────────────────────

@receiver(post_save, sender='accounting.OtherIncome')
def on_other_income(sender, instance, **kwargs):
    chama = getattr(instance, 'chama', None)
    _delete_entry('other_income', instance.pk, chama)
    if instance.is_voided or not chama:
        return
    _post(chama, instance.date,
          f"{instance.get_source_display()} — {instance.description}",
          f"OTH-{instance.pk}",
          'other_income', instance.pk,
          [
              ('1000', 'debit',  instance.amount, 'Cash received',  None),
              ('4500', 'credit', instance.amount, 'Other income',   None),
          ])


@receiver(post_delete, sender='accounting.OtherIncome')
def on_other_income_delete(sender, instance, **kwargs):
    _delete_entry('other_income', instance.pk, getattr(instance, 'chama', None))
