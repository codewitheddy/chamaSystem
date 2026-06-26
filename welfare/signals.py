"""
Auto-post welfare transactions to the accounting ledger.
Welfare contributions → CREDIT (welfare_contribution category)
Welfare disbursements → DEBIT  (welfare_disbursement category)
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from accounting.models import Transaction


# ── Add welfare categories to Transaction if not present ────────────────────
# We extend the category choices at runtime so no migration is needed.
_WELFARE_CATS = [
    ('welfare_contribution', 'Welfare Contribution'),
    ('welfare_disbursement', 'Welfare Disbursement'),
]
for _val, _label in _WELFARE_CATS:
    if not any(c[0] == _val for c in Transaction.CATEGORY_CHOICES):
        Transaction.CATEGORY_CHOICES.append((_val, _label))


# ── Welfare Contributions ────────────────────────────────────────────────────

def _wc_ref(wc):
    return f"welfare_contribution:{wc.pk}"


@receiver(post_save, sender='welfare.WelfareContribution')
def on_welfare_contribution(sender, instance, **kwargs):
    ref = _wc_ref(instance)
    if instance.is_voided:
        Transaction.objects.filter(reference=ref).delete()
        return
    Transaction.objects.update_or_create(
        reference=ref,
        defaults=dict(
            date=instance.date,
            category='welfare_contribution',
            direction=Transaction.CREDIT,
            amount=instance.amount,
            description=(
                f"Welfare contribution — {instance.member.name}"
                + (f" (Claim #{instance.claim_id})" if instance.claim_id else "")
            ),
            member=instance.member,
            is_manual=False,
        )
    )


@receiver(post_delete, sender='welfare.WelfareContribution')
def on_welfare_contribution_delete(sender, instance, **kwargs):
    Transaction.objects.filter(reference=_wc_ref(instance)).delete()


# ── Welfare Disbursements ────────────────────────────────────────────────────

def _wd_ref(claim):
    return f"welfare_disbursement:{claim.pk}"


@receiver(post_save, sender='welfare.WelfareClaim')
def on_welfare_claim(sender, instance, **kwargs):
    ref = _wd_ref(instance)
    if instance.status == 'disbursed' and instance.amount_disbursed:
        Transaction.objects.update_or_create(
            reference=ref,
            defaults=dict(
                date=instance.date_disbursed or instance.date_filed,
                category='welfare_disbursement',
                direction=Transaction.DEBIT,
                amount=instance.amount_disbursed,
                description=(
                    f"Welfare disbursement — {instance.beneficiary} "
                    f"({instance.get_claim_type_display()})"
                ),
                member=instance.member,
                is_manual=False,
            )
        )
    else:
        # Remove ledger entry if claim is reversed/rejected
        Transaction.objects.filter(reference=ref).delete()


@receiver(post_delete, sender='welfare.WelfareClaim')
def on_welfare_claim_delete(sender, instance, **kwargs):
    Transaction.objects.filter(reference=_wd_ref(instance)).delete()
