"""
cPanel Passenger WSGI entry point.
cPanel's Python App selector (Passenger) looks for `application` in this file.
"""
import os
import sys

# ── Add project root to Python path ──────────────────────────────────────────
# __file__ is the project root when cPanel sets up the venv
INTERP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv', 'bin', 'python3')
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Point Django at the correct settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chama_system.settings')

# ── Activate the virtualenv created by cPanel ─────────────────────────────────
this_dir = os.path.dirname(os.path.abspath(__file__))
activate_this = os.path.join(this_dir, 'venv', 'bin', 'activate_this.py')
if os.path.exists(activate_this):
    with open(activate_this) as f:
        exec(f.read(), {'__file__': activate_this})

sys.path.insert(0, this_dir)

from django.core.wsgi import get_wsgi_application  # noqa: E402
application = get_wsgi_application()
