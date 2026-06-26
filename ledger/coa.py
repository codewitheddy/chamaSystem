"""
Default Chart of Accounts for a chama.
Called when a new Chama is created.
"""
from decimal import Decimal

DEFAULT_ACCOUNTS = [
    # ── ASSETS ──────────────────────────────────────────────────────
    ('1000', 'Cash & Bank',              'asset',     True),
    ('1100', 'Loans Receivable',         'asset',     True),
    ('1200', 'Interest Receivable',      'asset',     True),
    ('1300', 'Investments',              'asset',     True),
    ('1400', 'Welfare Fund Cash',        'asset',     True),
    ('1500', 'Other Assets',             'asset',     True),

    # ── LIABILITIES ─────────────────────────────────────────────────
    ('2000', 'Welfare Fund Payable',     'liability', True),
    ('2100', 'Accrued Expenses',         'liability', True),
    ('2200', 'Other Liabilities',        'liability', True),

    # ── EQUITY ──────────────────────────────────────────────────────
    ('3000', 'Member Share Capital',     'equity',    True),
    ('3100', 'Member Contributions',     'equity',    True),
    ('3200', 'Retained Earnings',        'equity',    True),
    ('3300', 'Registration Fees Equity', 'equity',    True),

    # ── INCOME ──────────────────────────────────────────────────────
    ('4000', 'Contribution Income',      'income',    True),
    ('4100', 'Interest Income',          'income',    True),
    ('4200', 'Penalty Income',           'income',    True),
    ('4300', 'Registration Fee Income',  'income',    True),
    ('4400', 'Investment Income',        'income',    True),
    ('4500', 'Other Income',             'income',    True),

    # ── EXPENSES ────────────────────────────────────────────────────
    ('5000', 'Operating Expenses',       'expense',   True),
    ('5100', 'Welfare Disbursements',    'expense',   True),
    ('5200', 'Loan Write-offs',          'expense',   True),
    ('5300', 'Bank Charges',             'expense',   True),
    ('5400', 'Other Expenses',           'expense',   True),
]


def seed_chart_of_accounts(chama):
    """Create the default CoA for a newly registered chama."""
    from .models import Account
    for code, name, acct_type, is_system in DEFAULT_ACCOUNTS:
        Account.objects.get_or_create(
            chama=chama,
            code=code,
            defaults={
                'name': name,
                'account_type': acct_type,
                'is_system': is_system,
                'is_active': True,
            }
        )


def get_account(chama, code):
    """Fetch a system account by code, or None."""
    from .models import Account
    try:
        return Account.objects.get(chama=chama, code=code)
    except Account.DoesNotExist:
        return None
