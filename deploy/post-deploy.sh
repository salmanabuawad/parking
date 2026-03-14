#!/bin/bash
# Run on server after setup-ubuntu.sh: create DB, ensure .env, run migrations, start services.
# Usage: sudo DEPLOY_ROOT=/opt/parking bash deploy/post-deploy.sh

set -e
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/parking}"
APP_USER="${APP_USER:-parking}"
BACKEND_DIR="$DEPLOY_ROOT/backend"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Post-deploy: $DEPLOY_ROOT ==="

# Ensure .env exists (do not overwrite existing)
if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  sed -i 's|:5432/postgres|:5432/parking|' "$BACKEND_DIR/.env"
  chown "$APP_USER:$APP_USER" "$BACKEND_DIR/.env"
  echo "Created $BACKEND_DIR/.env from .env.example (using database 'parking'). Edit SECRET_KEY and passwords if needed."
fi

# Create PostgreSQL database 'parking' if it does not exist
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'parking'" | grep -q 1; then
  echo "Database 'parking' already exists."
else
  sudo -u postgres psql -c "CREATE DATABASE parking OWNER postgres;"
  echo "Created database 'parking'."
fi

# Run migrations
echo "Running migrations..."
sudo -u "$APP_USER" "$BACKEND_DIR/.venv/bin/python" -m alembic -c "$BACKEND_DIR/alembic.ini" upgrade head
echo "Migrations done."

# Start services
systemctl daemon-reload
systemctl enable parking-backend parking-worker
systemctl start parking-backend parking-worker
systemctl reload nginx
echo "--- Services ---"
systemctl is-active parking-backend parking-worker nginx

echo "=== Post-deploy done. App: http://185.229.226.37 or https://185.229.226.37:8443 ==="
