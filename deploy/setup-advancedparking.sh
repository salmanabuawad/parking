#!/bin/bash
# Deploy NEW version to /opt/advancedparking (parking.wavelync.com subdomain).
# The EXISTING deployment at /opt/parking is NOT touched.
# Run as root: sudo bash deploy/setup-advancedparking.sh

set -e
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/advancedparking}"
APP_USER="${APP_USER:-advancedparking}"
NGINX_SITE="advancedparking"
BACKEND_PORT=8002   # different port from existing parking (8001)

echo "=== Advanced Parking deploy: $DEPLOY_ROOT (nginx site: $NGINX_SITE, port: $BACKEND_PORT) ==="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$SCRIPT_DIR/../backend" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  REPO_ROOT="$DEPLOY_ROOT"
fi

# Install system packages (skip if already installed)
apt-get update
apt-get install -y \
  python3 python3-venv python3-pip \
  nginx \
  tesseract-ocr tesseract-ocr-heb \
  ffmpeg \
  curl

# Node 18+ (NodeSource)
if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d v) -lt 18 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

# App user
if ! id "$APP_USER" &>/dev/null; then
  useradd -r -s /bin/bash -d "$DEPLOY_ROOT" "$APP_USER" || true
fi
mkdir -p "$DEPLOY_ROOT"
chown "$APP_USER:$APP_USER" "$DEPLOY_ROOT"

# Copy app files (preserve existing .env)
if [[ -d "$REPO_ROOT/backend" ]] && [[ "$REPO_ROOT" != "$DEPLOY_ROOT" ]]; then
  rsync -a --exclude '.venv' --exclude '__pycache__' --exclude 'node_modules' \
    "$REPO_ROOT/backend/" "$DEPLOY_ROOT/backend/"
  rsync -a --exclude 'node_modules' --exclude 'dist' \
    "$REPO_ROOT/frontend/" "$DEPLOY_ROOT/frontend/"
  chown -R "$APP_USER:$APP_USER" "$DEPLOY_ROOT"
fi
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
    # Install cryptography for video signing
    .venv/bin/pip install cryptography 2>/dev/null || true
  "
  mkdir -p "$BACKEND_DIR/videos"/{raw,processed,frames,screenshots}
  chown -R "$APP_USER:$APP_USER" "$BACKEND_DIR/videos"
fi

# Frontend build (API base / for nginx proxy on subdomain)
FRONTEND_DIR="$DEPLOY_ROOT/frontend"
if [[ -d "$FRONTEND_DIR" ]]; then
  sudo -u "$APP_USER" bash -c "
    cd '$FRONTEND_DIR'
    npm ci 2>/dev/null || npm install
    VITE_API_BASE_URL= npm run build
  "
fi

# Systemd: backend on port BACKEND_PORT
cat > /etc/systemd/system/advancedparking-backend.service << EOF
[Unit]
Description=Advanced Parking Enforcement API
After=network.target postgresql.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$BACKEND_DIR
Environment=PATH=$BACKEND_DIR/.venv/bin:/usr/bin
Environment=PRODUCTION=1
Environment=PORT=$BACKEND_PORT
EnvironmentFile=-$BACKEND_DIR/.env
ExecStart=$BACKEND_DIR/.venv/bin/uvicorn main:app --host 127.0.0.1 --port $BACKEND_PORT --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Systemd: upload worker
cat > /etc/systemd/system/advancedparking-worker.service << EOF
[Unit]
Description=Advanced Parking Upload Worker
After=network.target postgresql.service advancedparking-backend.service

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

# Nginx: NEW site for parking.wavelync.com subdomain — does NOT touch existing 'parking' site
FRONTEND_DIST="$DEPLOY_ROOT/frontend/dist"
SSL_CERT="/etc/letsencrypt/live/wavelync.com/fullchain.pem"
SSL_KEY="/etc/letsencrypt/live/wavelync.com/privkey.pem"
if [[ ! -f "$SSL_CERT" ]]; then
  SSL_CERT="/etc/ssl/certs/ssl-cert-snakeoil.pem"
  SSL_KEY="/etc/ssl/private/ssl-cert-snakeoil.key"
fi

cat > /etc/nginx/sites-available/$NGINX_SITE << EOF
# Redirect HTTP → HTTPS for subdomain
server {
    listen 80;
    server_name parking.wavelync.com;
    return 301 https://parking.wavelync.com\$request_uri;
}

server {
    listen 443 ssl;
    server_name parking.wavelync.com;
    ssl_certificate     $SSL_CERT;
    ssl_certificate_key $SSL_KEY;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    client_max_body_size 100M;

    location = /index.html {
        root $FRONTEND_DIST;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }

    location /api/ {
        proxy_pass http://127.0.0.1:$BACKEND_PORT/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        proxy_intercept_errors on;
        error_page 502 503 504 = @api_error;
    }

    location @api_error {
        default_type application/json;
        return 503 '{"detail":"Service temporarily unavailable"}';
    }

    location / {
        root $FRONTEND_DIST;
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

# Enable new site — DO NOT remove the existing 'parking' site
ln -sf /etc/nginx/sites-available/$NGINX_SITE /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx || systemctl start nginx

echo "=== Setup done. Next steps ==="
echo "1. Create $BACKEND_DIR/.env with DATABASE_URL=postgresql://postgres:postgres@localhost:5432/advancedparking"
echo "2. Run: sudo DEPLOY_ROOT=$DEPLOY_ROOT APP_USER=$APP_USER bash $DEPLOY_ROOT/deploy/post-deploy-advancedparking.sh"
echo "3. Point parking.wavelync.com DNS A-record to 185.229.226.37"
echo "4. (If needed) expand SSL cert: certbot certonly --nginx --expand -d wavelync.com -d parking.wavelync.com"
echo "5. Open https://parking.wavelync.com"
