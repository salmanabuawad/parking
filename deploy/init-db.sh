#!/bin/bash
# Init or recreate DB on server. Run from server or: ssh root@185.229.226.37 "sudo RECREATE_DB=1 DEPLOY_ROOT=/opt/parking bash /opt/parking/deploy/init-db.sh"
# Usage: sudo DEPLOY_ROOT=/opt/parking bash deploy/init-db.sh
#        sudo RECREATE_DB=1 DEPLOY_ROOT=/opt/parking bash deploy/init-db.sh   # drop, create, migrate

set -e
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/parking}"
APP_USER="${APP_USER:-parking}"
BACKEND_DIR="$DEPLOY_ROOT/backend"

echo "=== Init DB: $DEPLOY_ROOT (RECREATE_DB=${RECREATE_DB:-0}) ==="

if [[ -n "$RECREATE_DB" ]] && [[ "$RECREATE_DB" != "0" ]]; then
  echo "Recreating database 'parking'..."
  sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'parking' AND pid <> pg_backend_pid();" 2>/dev/null || true
  sudo -u postgres psql -c "DROP DATABASE IF EXISTS parking;"
  sudo -u postgres psql -c "CREATE DATABASE parking OWNER postgres;"
  echo "Database 'parking' recreated."
elif sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'parking'" | grep -q 1; then
  echo "Database 'parking' already exists."
else
  sudo -u postgres psql -c "CREATE DATABASE parking OWNER postgres;"
  echo "Created database 'parking'."
fi

echo "Running migrations..."
sudo -u "$APP_USER" "$BACKEND_DIR/.venv/bin/python" -m alembic -c "$BACKEND_DIR/alembic.ini" upgrade head
echo "=== Init DB done. ==="
