# Deploy Parking Enforcement App on Ubuntu (185.229.226.37)

## Overview

- **Backend**: FastAPI on port 8000 (gunicorn + uvicorn workers)
- **Frontend**: Static build served by nginx
- **Upload worker**: Background process (systemd)
- **PostgreSQL**: Installed on the same server with default credentials (`postgres` / `postgres`, database `postgres`)
- **Nginx**: Reverse proxy on port 80 (HTTP) and **8443** (HTTPS; use 8443 when 443 is in use)

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

## 2. Run the setup script (or full redeploy with DB init)

From your **local machine** (with the repo), copy the deploy files to the server and run setup:

**Full redeploy and init DB (recreate DB from scratch):**
```powershell
.\deploy\deploy-to-remote.ps1 -RecreateDb
```

**Normal deploy (keeps existing DB, create only if missing):**
```powershell
.\deploy\deploy-to-remote.ps1
```

**On the server only – init or recreate DB (no app copy):**
```bash
# Init: create DB if missing, run migrations
sudo DEPLOY_ROOT=/opt/parking bash /opt/parking/deploy/init-db.sh

# Recreate: drop DB, create, run migrations
sudo RECREATE_DB=1 DEPLOY_ROOT=/opt/parking bash /opt/parking/deploy/init-db.sh
```

**Manual copy + setup (alternative):**
```bash
# Copy deploy folder and run (replace with your repo path)
scp -r parking/deploy parking/backend parking/frontend parking/nginx root@185.229.226.37:/tmp/
ssh root@185.229.226.37 'bash -s' < parking/deploy/setup-ubuntu.sh
```

Or on the **server** after cloning the repo:

```bash
cd /opt  # or your preferred directory
git clone <your-repo-url> parking
cd parking
sudo bash deploy/setup-ubuntu.sh
```

The script will:

- Install Python 3, Node 18+, PostgreSQL, nginx, Tesseract OCR, ffmpeg
- Create app user `parking`
- Create a virtualenv and install backend deps
- Build the frontend with `VITE_API_BASE_URL=/api`
- Create systemd units for backend and worker
- Install and enable **nginx**: apply `deploy/nginx-parking.conf` (proxy `/api/` → backend:8000, serve frontend from `frontend/dist`), disable default site, enable and reload nginx

## 3. Configure environment

PostgreSQL is on the same server with **default credentials** (user `postgres`, password `postgres`, default database `postgres`). The app can use the default database or you can create a dedicated one.

On the server, create the backend env file:

```bash
sudo -u parking bash
cd /opt/parking/backend   # or DEPLOY_ROOT from setup
cp .env.example .env
nano .env
```

**Option A – Use default Postgres database** (no DB setup needed):

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
SECRET_KEY=your-long-random-secret-key
VIDEOS_DIR=/opt/parking/backend/videos
PRODUCTION=1
```

**Option B – Create a dedicated database** (recommended for production):

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/parking
SECRET_KEY=your-long-random-secret-key
VIDEOS_DIR=/opt/parking/backend/videos
PRODUCTION=1
```

Then create the database (as postgres):

```bash
sudo -u postgres psql -c "CREATE DATABASE parking OWNER postgres;"
```

Run migrations:

```bash
cd /opt/parking/backend
source .venv/bin/activate
alembic upgrade head
# or: python -m alembic upgrade head
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

```bash
sudo systemctl daemon-reload
sudo systemctl enable parking-backend parking-worker
sudo systemctl start parking-backend parking-worker
sudo systemctl reload nginx
```

Check status:

```bash
sudo systemctl status parking-backend parking-worker nginx
```

## 5. Nginx

- Config used by setup: **`deploy/nginx-parking.conf`** (copied to `/etc/nginx/sites-available/parking` on the server).
- Listen: **80** (HTTP), **8443** (HTTPS; use when 443 is in use). Proxies **`/api/`** to `http://127.0.0.1:8000/api/`. Serves frontend from **`/opt/parking/frontend/dist`**.
- HTTPS uses the default snakeoil cert; if missing run `sudo apt-get install ssl-cert` or point `ssl_certificate` to your own certs.
- Test config: `sudo nginx -t`. Reload: `sudo systemctl reload nginx`.

## 6. Open the app

- **HTTP**: http://185.229.226.37  
- **HTTPS**: https://185.229.226.37:8443 (port 8443 used because 443 is in use; nginx listens on 8443 with SSL). For real certs, point `ssl_certificate` / `ssl_certificate_key` in `deploy/nginx-parking.conf` to your certs and reload nginx.

## 7. CORS (if needed)

If the frontend is ever served from another domain, add it to the backend CORS allow list. In `backend/main.py`, add your domain to `allow_origins` or set `allow_origin_regex`; or set env var if your app supports it.

## 8. Firewall

Allow HTTP/HTTPS and SSH:

```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 8443
sudo ufw enable
```

## 9. Troubleshooting

- **502 Bad Gateway**: Backend not running or not listening on 127.0.0.1:8000. Check `journalctl -u parking-backend -f`.
- **Videos not loading**: Ensure `VIDEOS_DIR` exists and is writable by user `parking`; worker and backend must use the same path.
- **Tesseract (plate OCR)**: Install with `apt install tesseract-ocr`; worker sets path to `/usr/bin/tesseract` on Linux.
- **Logs**:  
  - Backend: `journalctl -u parking-backend -f`  
  - Worker: `journalctl -u parking-worker -f`  
  - Nginx: `/var/log/nginx/error.log`
