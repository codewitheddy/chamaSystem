"""
Auto-post Transaction ledger entries from app events.
All writes use update_or_create on reference so re-saves don't duplicate.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Transaction


def _contribution_ref(c):  return f"contribution:{c.pk}"
def _loan_ref(l):           return f"loan_issued:{l.pk}"
def _payment_ref(p):        return f"payment:{p.pk}"
def _interest_ref(p):       return f"interest:{p.pk}"
def _penalty_ref(p):        return f"penalty:{p.pk}"
def _expense_ref(e):        return f"expense:{e.pk}"


# ── Contributions ─────────────────────────────────────────────────────────────

@receiver(post_save, sender='contributions.Contribution')
def on_contribution_save(sender, instance, created, **kwargs):
    chama = getattr(instance.member, 'chama', None)
    ref = _contribution_ref(instance)
    if instance.is_voided:
        Transaction.objects.filter(reference=ref).delete()
        return
    Transaction.objects.update_or_create(
        reference=ref,
        defaults=dict(
            chama=chama,
            date=instance.date,
            category=Transaction.CAT_CONTRIBUTION,
            direction=Transaction.CREDIT,
            amount=instance.amount,
            description=f"Contribution — {instance.member.name} ({instance.get_month_display()} {instance.year})",
            member=instance.member,
            is_manual=False,
        )
    )

@receiver(post_delete, sender='contributions.Contribution')
def on_contribution_delete(sender, instance, **kwargs):
    Transaction.objects.filter(reference=_contribution_ref(instance)).delete()


# ── Loan disbursements ────────────────────────────────────────────────────────

@receiver(post_save, sender='loans.Loan')
def on_loan_save(sender, instance, created, **kwargs):
    if not created:
        return
    chama = getattr(instance.member, 'chama', None)
    Transaction.objects.get_or_create(
        reference=_loan_ref(instance),
        defaults=dict(
            chama=chama,
            date=instance.date_taken,
            category=Transaction.CAT_LOAN_ISSUED,
            direction=Transaction.DEBIT,
            amount=instance.loan_amount,
            description=f"Loan disbursed — {instance.member.name}",
            member=instance.member,
            is_manual=False,
        )
    )

@receiver(post_delete, sender='loans.Loan')
def on_loan_delete(sender, instance, **kwargs):
    Transaction.objects.filter(reference=_loan_ref(instance)).delete()


# ── Loan repayments ───────────────────────────────────────────────────────────

@receiver(post_save, sender='payments.Payment')
def on_payment_save(sender, instance, created, **kwargs):
    chama = getattr(instance.member, 'chama', None)
    if instance.is_voided:
        Transaction.objects.filter(reference__in=[
            _payment_ref(instance), _interest_ref(instance)
        ]).delete()
        loan = instance.loan
        from django.db.models import Sum
        paid = loan.payment_set.filter(is_voided=False).aggregate(t=Sum('amount'))['t'] or 0
        loan.amount_paid = paid
        loan.save()
        return
    if not created:
        return
    loan = instance.loan
    from decimal import Decimal
    if loan.total_payable > 0 and loan.loan_amount > 0:
        interest_ratio = loan.interest_amount / loan.total_payable
        interest_portion = (instance.amount * interest_ratio).quantize(Decimal('0.01'))
        principal_portion = instance.amount - interest_portion
    else:
        principal_portion = instance.amount
        interest_portion = Decimal('0.00')

    Transaction.objects.get_or_create(
        reference=_payment_ref(instance),
        defaults=dict(
            chama=chama,
            date=instance.date,
            category=Transaction.CAT_LOAN_REPAYMENT,
            direction=Transaction.CREDIT,
            amount=principal_portion,
            description=f"Loan repayment — {instance.member.name} (Loan #{loan.pk})",
            member=instance.member,
            is_manual=False,
        )
    )
    if interest_portion > 0:
        Transaction.objects.get_or_create(
            reference=_interest_ref(instance),
            defaults=dict(
                chama=chama,
                date=instance.date,
                category=Transaction.CAT_INTEREST,
                direction=Transaction.CREDIT,
                amount=interest_portion,
                description=f"Interest income — {instance.member.name} (Loan #{loan.pk})",
                member=instance.member,
                is_manual=False,
            )
        )

@receiver(post_delete, sender='payments.Payment')
def on_payment_delete(sender, instance, **kwargs):
    Transaction.objects.filter(reference__in=[
        _payment_ref(instance), _interest_ref(instance)
    ]).delete()


# ── Penalties ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='meetings.MeetingPenalty')
def on_penalty_save(sender, instance, **kwargs):
    chama = getattr(instance.member, 'chama', None)
    if instance.is_voided:
        Transaction.objects.filter(reference=_penalty_ref(instance)).delete()
        return
    if instance.paid:
        Transaction.objects.update_or_create(
            reference=_penalty_ref(instance),
            defaults=dict(
                chama=chama,
                date=instance.meeting.date,
                category=Transaction.CAT_PENALTY,
                direction=Transaction.CREDIT,
                amount=instance.amount,
                description=f"Penalty — {instance.member.name} ({instance.get_reason_display()})",
                member=instance.member,
                is_manual=False,
            )
        )
    else:
        Transaction.objects.filter(reference=_penalty_ref(instance)).delete()

@receiver(post_delete, sender='meetings.MeetingPenalty')
def on_penalty_delete(sender, instance, **kwargs):
    Transaction.objects.filter(reference=_penalty_ref(instance)).delete()


# ── Expenses ──────────────────────────────────────────────────────────────────

@receiver(post_save, sender='accounting.Expense')
def on_expense_save(sender, instance, **kwargs):
    chama = getattr(instance, 'chama', None)
    if instance.is_voided:
        Transaction.objects.filter(reference=_expense_ref(instance)).delete()
        return
    Transaction.objects.update_or_create(
        reference=_expense_ref(instance),
        defaults=dict(
            chama=chama,
            date=instance.date,
            category=Transaction.CAT_EXPENSE,
            direction=Transaction.DEBIT,
            amount=instance.amount,
            description=instance.description,
            member=None,
            is_manual=True,
        )
    )

@receiver(post_delete, sender='accounting.Expense')
def on_expense_delete(sender, instance, **kwargs):
    Transaction.objects.filter(reference=_expense_ref(instance)).delete()
