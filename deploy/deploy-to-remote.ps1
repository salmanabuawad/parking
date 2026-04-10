# Deploy Parking app to remote server 185.229.226.37
# Run from repo root: .\deploy\deploy-to-remote.ps1
# Optional: .\deploy\deploy-to-remote.ps1 -RecreateDb   to drop/recreate DB and run migrations
# You will be prompted for the SSH password (root or parking) unless you use keys.

param([switch]$RecreateDb)

$REMOTE = "root@185.229.226.37"
$DEPLOY_ROOT = "/opt/parking"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

Write-Host "=== Deploying from $repoRoot to $REMOTE ===" -ForegroundColor Cyan

# Copy app and deploy files to /tmp on server (exclude node_modules, dist, .venv, __pycache__)
Write-Host "Copying backend, frontend, deploy (excluding node_modules)..." -ForegroundColor Yellow
$driveLetter = $repoRoot.Substring(0,1).ToLower()
$repoRootUnix = '/' + $driveLetter + ($repoRoot.Substring(2) -replace '\\', '/')
bash -c "tar -czf - --exclude='*/node_modules' --exclude='*/dist' --exclude='*/.venv' --exclude='*/__pycache__' -C '$repoRootUnix' backend frontend deploy | ssh $REMOTE 'tar -xzf - -C /tmp/'"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Upload failed. Check SSH access (e.g. ssh $REMOTE)" -ForegroundColor Red
    exit 1
}

# Run setup on server: copy from /tmp to DEPLOY_ROOT (preserve existing .env), then run setup
Write-Host "Running setup on server..." -ForegroundColor Yellow
$remoteCmd = "sudo mkdir -p $DEPLOY_ROOT && (sudo test -f $DEPLOY_ROOT/backend/.env && sudo cp $DEPLOY_ROOT/backend/.env /tmp/backend.env.bak || true) && sudo cp -r /tmp/backend /tmp/frontend /tmp/deploy $DEPLOY_ROOT/ && (sudo test -f /tmp/backend.env.bak && sudo mv /tmp/backend.env.bak $DEPLOY_ROOT/backend/.env || true) && sudo DEPLOY_ROOT=$DEPLOY_ROOT bash $DEPLOY_ROOT/deploy/setup-ubuntu.sh"
ssh $REMOTE $remoteCmd

if ($LASTEXITCODE -ne 0) {
    Write-Host "SSH/setup failed." -ForegroundColor Red
    exit 1
}

# Post-deploy: create/recreate DB, .env if missing, migrations, start services
if ($RecreateDb) { Write-Host "Init DB (recreate), migrations, starting services..." -ForegroundColor Yellow } else { Write-Host "Creating DB, running migrations, starting services..." -ForegroundColor Yellow }
$postEnv = if ($RecreateDb) { "sudo RECREATE_DB=1 DEPLOY_ROOT=$DEPLOY_ROOT bash $DEPLOY_ROOT/deploy/post-deploy.sh" } else { "sudo DEPLOY_ROOT=$DEPLOY_ROOT bash $DEPLOY_ROOT/deploy/post-deploy.sh" }
ssh $REMOTE $postEnv

if ($LASTEXITCODE -ne 0) {
    Write-Host "Post-deploy failed (check DB, .env, migrations)." -ForegroundColor Red
    exit 1
}

Write-Host "=== Deploy done. App: http://185.229.226.37 or https://185.229.226.37:8443 ===" -ForegroundColor Green
