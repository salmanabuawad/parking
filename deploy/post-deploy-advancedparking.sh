#!/bin/bash
# Post-deploy for /opt/advancedparking: create DB 'advancedparking', write .env, run migrations, start services.
# Does NOT touch the existing /opt/parking deployment.
# Usage: sudo DEPLOY_ROOT=/opt/advancedparking bash deploy/post-deploy-advancedparking.sh
#        sudo RECREATE_DB=1 DEPLOY_ROOT=/opt/advancedparking bash deploy/post-deploy-advancedparking.sh

set -e
DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/advancedparking}"
APP_USER="${APP_USER:-advancedparking}"
DB_NAME="advancedparking"
BACKEND_DIR="$DEPLOY_ROOT/backend"

echo "=== Post-deploy advancedparking: $DEPLOY_ROOT (DB: $DB_NAME) ==="

# Write .env if missing
if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  if [[ -f "$BACKEND_DIR/.env.example" ]]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  else
    cat > "$BACKEND_DIR/.env" << ENVEOF
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/$DB_NAME
SECRET_KEY=change-me-$(openssl rand -hex 24)
VIDEOS_DIR=$DEPLOY_ROOT/backend/videos
PRODUCTION=1
ENVEOF
  fi
  # Point to advancedparking DB
  sed -i "s|:5432/[a-zA-Z_]*|:5432/$DB_NAME|g" "$BACKEND_DIR/.env"
  chown "$APP_USER:$APP_USER" "$BACKEND_DIR/.env"
  echo "Created $BACKEND_DIR/.env — review SECRET_KEY before going live."
fi

# Set postgres password (idempotent)
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';" 2>/dev/null || true

# Create database 'advancedparking'
if [[ -n "$RECREATE_DB" ]] && [[ "$RECREATE_DB" != "0" ]]; then
  echo "Recreating database '$DB_NAME'..."
  sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" 2>/dev/null || true
  sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;"
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER postgres;"
  echo "Database '$DB_NAME' recreated."
elif sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
  echo "Database '$DB_NAME' already exists."
else
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER postgres;"
  echo "Created database '$DB_NAME'."
fi

# Run Alembic migrations
echo "Running migrations..."
sudo -u "$APP_USER" bash -c "cd '$BACKEND_DIR' && '$BACKEND_DIR/.venv/bin/python' -m alembic -c '$BACKEND_DIR/alembic.ini' upgrade head"
echo "Migrations done."

# Seed violation rules
echo "Seeding violation rules..."
sudo -u "$APP_USER" bash -c "cd '$BACKEND_DIR' && '$BACKEND_DIR/.venv/bin/python' seed_violation_rules.py" 2>/dev/null || \
  echo "  (seed_violation_rules.py not found or failed — run manually if needed)"

# Create videos directories
mkdir -p "$BACKEND_DIR/videos"/{raw,processed,frames,screenshots}
chown -R "$APP_USER:$APP_USER" "$BACKEND_DIR/videos"

# Start services (separate from existing parking services)
systemctl daemon-reload
systemctl enable advancedparking-backend advancedparking-worker
systemctl start advancedparking-backend advancedparking-worker
systemctl reload nginx

echo "--- Service status ---"
systemctl is-active advancedparking-backend advancedparking-worker nginx

echo "=== Post-deploy done ==="
echo "App: https://parking.wavelync.com"
echo "Existing deployment at /opt/parking is untouched."
