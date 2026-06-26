"""
Auto-post investment transactions to the accounting ledger.
Capital injections  → DEBIT  (investment_capital)
Income / dividends  → CREDIT (investment_income)
Exit proceeds       → CREDIT (investment_income)
Investment expenses → DEBIT  (investment_expense)
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from accounting.models import Transaction

# Extend Transaction categories at runtime
_CATS = [
    ('investment_capital', 'Investment Capital'),
    ('investment_income',  'Investment Income'),
    ('investment_expense', 'Investment Expense'),
]
for _val, _label in _CATS:
    if not any(c[0] == _val for c in Transaction.CATEGORY_CHOICES):
        Transaction.CATEGORY_CHOICES.append((_val, _label))


def _ref(tx):
    return f"investment_tx:{tx.pk}"


@receiver(post_save, sender='investments.InvestmentTransaction')
def on_investment_tx(sender, instance, **kwargs):
    from investments.models import InvestmentTransaction
    ref = _ref(instance)

    # Map tx_type → ledger category + direction
    mapping = {
        InvestmentTransaction.TYPE_INJECTION: ('investment_capital', Transaction.DEBIT),
        InvestmentTransaction.TYPE_INCOME:    ('investment_income',  Transaction.CREDIT),
        InvestmentTransaction.TYPE_DIVIDEND:  ('investment_income',  Transaction.CREDIT),
        InvestmentTransaction.TYPE_EXIT:      ('investment_income',  Transaction.CREDIT),
        InvestmentTransaction.TYPE_EXPENSE:   ('investment_expense', Transaction.DEBIT),
    }
    category, direction = mapping.get(instance.tx_type, ('investment_income', Transaction.CREDIT))

    Transaction.objects.update_or_create(
        reference=ref,
        defaults=dict(
            date=instance.date,
            category=category,
            direction=direction,
            amount=instance.amount,
            description=(
                f"{instance.get_tx_type_display()} — {instance.investment.name}"
                + (f": {instance.description}" if instance.description else "")
            ),
            member=None,
            is_manual=False,
        )
    )


@receiver(post_delete, sender='investments.InvestmentTransaction')
def on_investment_tx_delete(sender, instance, **kwargs):
    Transaction.objects.filter(reference=_ref(instance)).delete()
