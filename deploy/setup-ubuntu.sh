#!/bin/bash
# Deploy Parking Enforcement app on Ubuntu (185.229.226.37)
# Run as root or with sudo. App directory: set DEPLOY_ROOT or defaults to /opt/parking.

set -e
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/parking}"
APP_USER="${APP_USER:-parking}"

echo "=== Parking app deploy: $DEPLOY_ROOT ==="

# Detect script location: if run from repo, SCRIPT_DIR is deploy/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$SCRIPT_DIR/../backend" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  REPO_ROOT="$DEPLOY_ROOT"
fi

# Install system packages (Ubuntu/Debian)
apt-get update
apt-get install -y \
  python3 python3-venv python3-pip \
  postgresql postgresql-contrib \
  nginx \
  tesseract-ocr tesseract-ocr-heb \
  ffmpeg \
  curl

# Node 18.x (NodeSource)
if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d v) -lt 18 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

# Optional: install deploy/authorized_keys for root (passwordless SSH for deployer)
if [[ -f "$SCRIPT_DIR/authorized_keys" ]]; then
  mkdir -p /root/.ssh
  chmod 700 /root/.ssh
  cat "$SCRIPT_DIR/authorized_keys" >> /root/.ssh/authorized_keys
  sort -u /root/.ssh/authorized_keys -o /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
  echo "Installed deploy/authorized_keys into /root/.ssh/authorized_keys"
fi

# App user
if ! id "$APP_USER" &>/dev/null; then
  useradd -r -s /bin/bash -d "$DEPLOY_ROOT" "$APP_USER" || true
fi
mkdir -p "$DEPLOY_ROOT"
chown "$APP_USER:$APP_USER" "$DEPLOY_ROOT"

# Copy app if we have a repo
if [[ -d "$REPO_ROOT/backend" ]] && [[ "$REPO_ROOT" != "$DEPLOY_ROOT" ]]; then
  rsync -a --exclude '.venv' --exclude '__pycache__' --exclude 'node_modules' \
    "$REPO_ROOT/backend/" "$DEPLOY_ROOT/backend/"
  rsync -a --exclude 'node_modules' --exclude 'dist' \
    "$REPO_ROOT/frontend/" "$DEPLOY_ROOT/frontend/"
  cp -r "$REPO_ROOT/nginx" "$DEPLOY_ROOT/" 2>/dev/null || true
  chown -R "$APP_USER:$APP_USER" "$DEPLOY_ROOT"
fi
# Ensure app in DEPLOY_ROOT is owned by APP_USER (e.g. when copied by deploy-to-remote)
if [[ -d "$DEPLOY_ROOT/backend" ]]; then
  chown -R "$APP_USER:$APP_USER" "$DEPLOY_ROOT"
fi

# Backend venv and deps
BACKEND_DIR="$DEPLOY_ROOT/backend"
if [[ -d "$BACKEND_DIR" ]]; then
  sudo -u "$APP_USER" bash -c "
    cd '$BACKEND_DIR'
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
  "
  mkdir -p "$BACKEND_DIR/videos"/{raw,processed,frames,screenshots}
  chown -R "$APP_USER:$APP_USER" "$BACKEND_DIR/videos"
fi

# Frontend build (API base /api for nginx proxy)
FRONTEND_DIR="$DEPLOY_ROOT/frontend"
if [[ -d "$FRONTEND_DIR" ]]; then
  sudo -u "$APP_USER" bash -c "
    cd '$FRONTEND_DIR'
    npm ci 2>/dev/null || npm install
    VITE_API_BASE_URL=/api npm run build
  "
fi

# Systemd: backend (uvicorn via run_backend.py; for production consider gunicorn + uvicorn workers)
cat > /etc/systemd/system/parking-backend.service << EOF
[Unit]
Description=Parking Enforcement API
After=network.target postgresql.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$BACKEND_DIR
Environment=PATH=$BACKEND_DIR/.venv/bin:/usr/bin
Environment=PRODUCTION=1
EnvironmentFile=-$BACKEND_DIR/.env
ExecStart=$BACKEND_DIR/.venv/bin/python run_backend.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Worker
cat > /etc/systemd/system/parking-worker.service << EOF
[Unit]
Description=Parking Upload Worker
After=network.target postgresql.service parking-backend.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$BACKEND_DIR
Environment=PATH=$BACKEND_DIR/.venv/bin:/usr/bin
EnvironmentFile=$BACKEND_DIR/.env
ExecStart=$BACKEND_DIR/.venv/bin/python run_upload_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Nginx: serve static frontend + proxy /api (HTTPS on 8443 when 443 is in use)
FRONTEND_DIST="$DEPLOY_ROOT/frontend/dist"
cat > /etc/nginx/sites-available/parking << EOF
server {
    listen 80;
    listen 8443 ssl;
    server_name 185.229.226.37 localhost;
    ssl_certificate     /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;
    client_max_body_size 100M;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    location / {
        root $FRONTEND_DIST;
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

ln -sf /etc/nginx/sites-available/parking /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# Enable and start nginx
systemctl enable nginx
nginx -t && systemctl reload nginx || systemctl start nginx

echo "=== Setup done. Next steps ==="
echo "1. Create $BACKEND_DIR/.env (DATABASE_URL, SECRET_KEY, VIDEOS_DIR)"
echo "2. Create DB and run migrations (see deploy/README.md)"
echo "3. systemctl daemon-reload && systemctl enable parking-backend parking-worker && systemctl start parking-backend parking-worker && systemctl reload nginx"
echo "4. Open http://185.229.226.37"
