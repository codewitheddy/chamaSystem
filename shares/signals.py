from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ShareTransaction, ShareAccount
from accounting.models import Transaction


@receiver(post_save, sender=ShareTransaction)
def post_share_transaction(sender, instance, created, **kwargs):
    if not created:
        return

    acct = instance.account

    # Update share count
    if instance.transaction_type in (
        ShareTransaction.TYPE_PURCHASE,
        ShareTransaction.TYPE_TRANSFER_IN,
        ShareTransaction.TYPE_BONUS,
        ShareTransaction.TYPE_ADJUSTMENT,
    ):
        acct.shares_held += instance.shares
    elif instance.transaction_type in (
        ShareTransaction.TYPE_TRANSFER_OUT,
        ShareTransaction.TYPE_REFUND,
    ):
        acct.shares_held = max(0, acct.shares_held - instance.shares)
    acct.save()

    # Post to accounting ledger
    is_credit = instance.transaction_type in (
        ShareTransaction.TYPE_PURCHASE,
        ShareTransaction.TYPE_TRANSFER_IN,
        ShareTransaction.TYPE_BONUS,
    )
    is_debit = instance.transaction_type in (
        ShareTransaction.TYPE_REFUND,
        ShareTransaction.TYPE_TRANSFER_OUT,
    )

    if is_credit or is_debit:
        Transaction.objects.create(
            chama=acct.member.chama,
            date=instance.date,
            category=Transaction.CAT_SHARE_CAPITAL,
            direction=Transaction.CREDIT if is_credit else Transaction.DEBIT,
            amount=instance.amount,
            description=f'Share capital — {instance.get_transaction_type_display()} — {acct.member.name}',
            reference=instance.reference or f'ShareTx #{instance.pk}',
            member=acct.member,
        )
