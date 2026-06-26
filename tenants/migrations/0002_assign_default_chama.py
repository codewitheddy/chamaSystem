"""
Data migration: creates a default Chama and assigns all existing
records (members, meetings, transactions, etc.) to it.

This ensures the system keeps working after the multi-tenancy migration
without any data loss.
"""
from django.db import migrations


def assign_default_chama(apps, schema_editor):
    Chama = apps.get_model('tenants', 'Chama')
    Member = apps.get_model('members', 'Member')
    Meeting = apps.get_model('meetings', 'Meeting')
    Transaction = apps.get_model('accounting', 'Transaction')
    Expense = apps.get_model('accounting', 'Expense')
    Investment = apps.get_model('investments', 'Investment')
    AGM = apps.get_model('agm', 'AGM')
    Post = apps.get_model('board', 'Post')
    WelfareClaim = apps.get_model('welfare', 'WelfareClaim')
    WelfareSettings = apps.get_model('welfare', 'WelfareSettings')
    ShareConfig = apps.get_model('shares', 'ShareConfig')
    LoanProduct = apps.get_model('loans', 'LoanProduct')
    Notification = apps.get_model('notifications', 'Notification')
    UserProfile = apps.get_model('accounts', 'UserProfile')

    # Create the default chama
    chama, _ = Chama.objects.get_or_create(
        slug='default',
        defaults={
            'name': 'My Chama',
            'tagline': 'Default chama — rename in Super Admin',
            'is_active': True,
        }
    )

    # Assign all existing records
    Member.objects.filter(chama__isnull=True).update(chama=chama)
    Meeting.objects.filter(chama__isnull=True).update(chama=chama)
    Transaction.objects.filter(chama__isnull=True).update(chama=chama)
    Expense.objects.filter(chama__isnull=True).update(chama=chama)
    Investment.objects.filter(chama__isnull=True).update(chama=chama)
    AGM.objects.filter(chama__isnull=True).update(chama=chama)
    Post.objects.filter(chama__isnull=True).update(chama=chama)
    WelfareClaim.objects.filter(chama__isnull=True).update(chama=chama)
    WelfareSettings.objects.filter(chama__isnull=True).update(chama=chama)
    ShareConfig.objects.filter(chama__isnull=True).update(chama=chama)
    LoanProduct.objects.filter(chama__isnull=True).update(chama=chama)
    Notification.objects.filter(chama__isnull=True).update(chama=chama)

    # Assign all staff users to the default chama
    UserProfile.objects.filter(chama__isnull=True).update(chama=chama)


def reverse_migration(apps, schema_editor):
    pass  # reversing just leaves chama set — safe


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('members', '0006_member_chama_alter_member_phone'),
        ('meetings', '0005_meeting_chama'),
        ('accounting', '0003_expense_chama_transaction_chama_and_more'),
        ('investments', '0002_investment_chama'),
        ('agm', '0002_agm_chama'),
        ('board', '0002_post_chama'),
        ('welfare', '0002_welfareclaim_chama_welfaresettings_chama'),
        ('shares', '0002_shareconfig_chama'),
        ('loans', '0008_loanproduct_chama_alter_loanproduct_max_amount_basis'),
        ('notifications', '0002_notification_chama'),
        ('accounts', '0003_userprofile_chama'),
    ]

    operations = [
        migrations.RunPython(assign_default_chama, reverse_migration),
    ]
