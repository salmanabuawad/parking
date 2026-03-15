# Deploy Parking Enforcement App

## Two deployments on one server

| | Existing (backup) | New (advanced) |
|---|---|---|
| **URL** | http://185.229.226.37 | https://parking.wavelync.com |
| **Directory** | `/opt/parking` | `/opt/advancedparking` |
| **Database** | `parking` | `advancedparking` |
| **Backend port** | 8001 | 8002 |
| **Systemd** | `parking-backend` / `parking-worker` | `advancedparking-backend` / `advancedparking-worker` |
| **Nginx site** | `parking` | `advancedparking` |
| **Deploy script** | `deploy-to-remote.ps1` | `deploy-to-advancedparking.ps1` |

The two deployments coexist on the same server and share the same PostgreSQL instance. Neither deploy script touches the other's files, database, or systemd services.

---

## Prerequisites for the subdomain deployment

### DNS

Add an **A record**: `parking.wavelync.com` → `185.229.226.37` in your DNS provider.

### SSL certificate (must cover the subdomain)

The existing Let's Encrypt cert covers `wavelync.com` only. Expand it to include the subdomain:

```bash
sudo certbot certonly --nginx --expand -d wavelync.com -d parking.wavelync.com
# or get a wildcard (covers all subdomains):
sudo certbot certonly --nginx -d wavelync.com -d '*.wavelync.com'
```

After reissuing: `sudo systemctl reload nginx`

## 1. Server preparation

SSH into the server as root:

```bash
ssh root@185.229.226.37
```

**Optional – passwordless SSH:** The repo includes `deploy/authorized_keys` (public key for salman.abuawad@gmail.com). When you run `deploy/setup-ubuntu.sh` on the server, it appends these keys to `/root/.ssh/authorized_keys`, so you can SSH as root without a password after the first setup.

**Optional – create a `parking` user with sudo** (so you don’t run the app as root):

```bash
# Copy the script to the server, then run (password is only in the command, not in the repo):
scp deploy/create-parking-user.sh root@185.229.226.37:/tmp/
ssh root@185.229.226.37 "sudo bash /tmp/create-parking-user.sh 'YOUR_PASSWORD'"
# Then log in as parking: ssh parking@185.229.226.37
```

## 2. Deploy the new version (advancedparking)

### From your local machine (PowerShell)

**Normal deploy — keeps existing DB, only creates `advancedparking` if missing:**
```powershell
.\deploy\deploy-to-advancedparking.ps1
```

**Full redeploy with fresh database:**
```powershell
.\deploy\deploy-to-advancedparking.ps1 -RecreateDb
```

This script:
1. SCPs `backend/`, `frontend/`, `deploy/` to the server
2. Runs `setup-advancedparking.sh` — installs deps, builds frontend, writes systemd units, creates nginx site `advancedparking` (does **not** touch existing `parking` site)
3. Runs `post-deploy-advancedparking.sh` — creates `advancedparking` DB, runs Alembic migrations, seeds violation rules, starts `advancedparking-backend` + `advancedparking-worker`

### Existing deployment (backup)

To redeploy the old version to `/opt/parking`:
```powershell
.\deploy\deploy-to-remote.ps1          # keep existing DB
.\deploy\deploy-to-remote.ps1 -RecreateDb  # recreate 'parking' DB
```

## 3. Configure environment

The `post-deploy-advancedparking.sh` script creates `/opt/advancedparking/backend/.env` automatically if it doesn't exist (using `.env.example` as template and pointing to the `advancedparking` database). Review and update the generated file:

```bash
sudo nano /opt/advancedparking/backend/.env
```

Minimum required:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/advancedparking
SECRET_KEY=your-long-random-secret-key
VIDEOS_DIR=/opt/advancedparking/backend/videos
PRODUCTION=1
```

To run migrations manually:

```bash
cd /opt/advancedparking/backend
sudo -u advancedparking .venv/bin/python -m alembic upgrade head
```

To seed violation rules:

```bash
sudo -u advancedparking .venv/bin/python seed_violation_rules.py
```

Create an admin user (if you have a script):

```bash
python -c "
from app.database import SessionLocal
from app.repositories import AdminRepository
from app.models import Admin
from passlib.context import CryptContext
pwd = CryptContext(schemes=['bcrypt']).hash('your-admin-password')
db = SessionLocal()
repo = AdminRepository(db)
repo.db.add(Admin(username='admin', hashed_password=pwd))
repo.db.commit()
print('Admin created.')
"
```

## 4. Start services

Services are started automatically by `post-deploy-advancedparking.sh`. To manage manually:

```bash
# New deployment (advancedparking)
sudo systemctl daemon-reload
sudo systemctl enable advancedparking-backend advancedparking-worker
sudo systemctl start advancedparking-backend advancedparking-worker
sudo systemctl reload nginx

# Check status
sudo systemctl status advancedparking-backend advancedparking-worker nginx
```

The existing `parking-backend` / `parking-worker` services are unaffected.

## 5. Nginx

Two nginx sites coexist:

| Site file | Serves | Proxies to |
|---|---|---|
| `/etc/nginx/sites-available/parking` | `185.229.226.37` (HTTP) | `127.0.0.1:8001` |
| `/etc/nginx/sites-available/advancedparking` | `parking.wavelync.com` (HTTPS) | `127.0.0.1:8002` |

Test config: `sudo nginx -t`. Reload: `sudo systemctl reload nginx`.

## 6. Open the app

- **Primary URL**: https://parking.wavelync.com
- **Direct IP (fallback)**: https://185.229.226.37 (uses the same cert — only valid if cert covers the IP or you accept the warning)
- HTTP on port 80 redirects automatically to HTTPS.

## 7. CORS (if needed)

If the frontend is ever served from another domain, add it to the backend CORS allow list. In `backend/main.py`, add your domain to `allow_origins` or set `allow_origin_regex`; or set env var if your app supports it.

## 8. Firewall

Allow HTTP/HTTPS and SSH:

```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

## 9. Troubleshooting

- **502 Bad Gateway on parking.wavelync.com**: `advancedparking-backend` not running. Check `journalctl -u advancedparking-backend -f`.
- **Videos not loading**: Ensure `VIDEOS_DIR=/opt/advancedparking/backend/videos` exists and is writable by user `advancedparking`.
- **Video signing error**: Requires `cryptography` package — if missing: `sudo -u advancedparking /opt/advancedparking/backend/.venv/bin/pip install cryptography`
- **Tesseract (plate OCR)**: Install with `apt install tesseract-ocr tesseract-ocr-heb`.
- **Logs**:
  - New backend: `journalctl -u advancedparking-backend -f`
  - New worker:  `journalctl -u advancedparking-worker -f`
  - Old backend: `journalctl -u parking-backend -f`
  - Nginx: `/var/log/nginx/error.log`
