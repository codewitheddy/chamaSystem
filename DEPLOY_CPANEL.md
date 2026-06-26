# cPanel Deployment Guide — Chama System

## Prerequisites
- cPanel with **Python App** selector (Phusion Passenger)
- PostgreSQL enabled on your hosting plan
- SSH access (recommended) or cPanel File Manager

---

## Step 1 — Create the PostgreSQL Database

1. Login to cPanel → **PostgreSQL Databases**
2. Create a new database: `cpanelusername_chamadb`
3. Create a new user: `cpanelusername_chamauser` with a strong password
4. Add the user to the database with **All Privileges**

> Note: cPanel automatically prefixes your database and username with your cPanel username.

---

## Step 2 — Upload the Project

Upload the entire project folder to your home directory (e.g. `/home/cpanelusername/chamas/`).

Using Git (recommended via SSH):
```bash
cd /home/cpanelusername
git clone https://your-repo-url.git chamas
```

Or use cPanel File Manager / FTP to upload a zip and extract it.

---

## Step 3 — Set Up Python App in cPanel

1. cPanel → **Setup Python App**
2. Click **Create Application**
   - Python version: **3.11** (or latest available)
   - Application root: `chamas`
   - Application URL: `/` (or subdirectory if needed)
   - Application startup file: `passenger_wsgi.py`
   - Application Entry point: `application`
3. Click **Create**

cPanel will create a virtual environment at `/home/cpanelusername/chamas/venv/`.

---

## Step 4 — Install Dependencies

In the cPanel Python App panel, click **Enter to the virtual environment** and run:

```bash
pip install -r requirements.txt
```

Or via SSH after activating the venv:
```bash
source /home/cpanelusername/chamas/venv/bin/activate
pip install -r requirements.txt
```

---

## Step 5 — Configure Environment Variables

Create the `.env` file in the project root:
```bash
cp .env.example .env
nano .env   # or edit via File Manager
```

Fill in all values — especially:
- `SECRET_KEY` — generate one: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- `DEBUG=False`
- `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com`
- `CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com`
- PostgreSQL `DB_*` credentials from Step 1
- `ADMIN_URL` — change to a hard-to-guess path

---

## Step 6 — Create Required Directories

```bash
mkdir -p /home/cpanelusername/chamas/logs
mkdir -p /home/cpanelusername/chamas/media
mkdir -p /home/cpanelusername/chamas/staticfiles
```

---

## Step 7 — Run Django Setup Commands

With the venv activated:
```bash
cd /home/cpanelusername/chamas

# Apply all database migrations
python manage.py migrate

# Collect static files into staticfiles/
python manage.py collectstatic --noinput

# Create a superuser
python manage.py createsuperuser
```

---

## Step 8 — Serve Static & Media Files

### Option A — `.htaccess` aliases (recommended for shared hosting)

Add this to your domain's `.htaccess` (in `public_html` or the app root):

```apache
# Static files
Alias /static/ /home/cpanelusername/chamas/staticfiles/
<Directory /home/cpanelusername/chamas/staticfiles>
    Require all granted
</Directory>

# Media files
Alias /media/ /home/cpanelusername/chamas/media/
<Directory /home/cpanelusername/chamas/media>
    Require all granted
</Directory>
```

### Option B — WhiteNoise (already configured)

WhiteNoise is configured in `settings.py` and will serve static files directly through Django with compression and cache headers. No `.htaccess` needed for static files. Media files still need the alias above.

---

## Step 9 — Restart the App

In cPanel → Setup Python App → click **Restart** next to your app.

---

## Step 10 — Verify

Visit `https://yourdomain.com` — you should see the landing page.
Visit `https://yourdomain.com/<ADMIN_URL>/` — Django admin should load.

---

## Ongoing Maintenance

### After code updates:
```bash
git pull
pip install -r requirements.txt   # if dependencies changed
python manage.py migrate           # if new migrations
python manage.py collectstatic --noinput
# Then restart the app in cPanel
```

### Scheduled tasks (cron jobs)
In cPanel → **Cron Jobs**, add:

```
# Contribution reminders — runs daily at 8 AM EAT
0 5 * * * /home/cpanelusername/chamas/venv/bin/python /home/cpanelusername/chamas/manage.py send_contribution_reminders >> /home/cpanelusername/chamas/logs/cron.log 2>&1
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 500 error on first load | Check `logs/security.log`; run `python manage.py check --deploy` |
| Static files 404 | Run `collectstatic`; verify `.htaccess` alias or WhiteNoise config |
| CSRF errors on forms | Verify `CSRF_TRUSTED_ORIGINS` includes `https://yourdomain.com` |
| DB connection refused | Check `DB_HOST=localhost` and that the DB user has privileges |
| `psycopg2` install fails | Try `pip install psycopg2-binary==2.9.11` as a fallback |
| Passenger not reloading | Create/touch `tmp/restart.txt` in the app root: `touch tmp/restart.txt` |

---

## Security Checklist Before Go-Live

- [ ] `DEBUG=False` in `.env`
- [ ] `SECRET_KEY` is a random 50+ character string (not the placeholder)
- [ ] `ADMIN_URL` changed to something hard to guess
- [ ] `ALLOWED_HOSTS` contains only your real domain(s)
- [ ] `CSRF_TRUSTED_ORIGINS` set with `https://` prefix
- [ ] PostgreSQL password is strong
- [ ] `.env` file is NOT committed to git (check `.gitignore`)
- [ ] SSL certificate active on the domain (cPanel → AutoSSL)
