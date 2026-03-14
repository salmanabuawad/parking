# Deploy Parking app to remote server 185.229.226.37
# Run from repo root: .\deploy\deploy-to-remote.ps1
# You will be prompted for the SSH password (root or parking) unless you use keys.

$REMOTE = "root@185.229.226.37"
$DEPLOY_ROOT = "/opt/parking"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

Write-Host "=== Deploying from $repoRoot to $REMOTE ===" -ForegroundColor Cyan

# Copy app and deploy files to /tmp on server
Write-Host "Copying backend, frontend, deploy..." -ForegroundColor Yellow
scp -r "$repoRoot\backend" "$repoRoot\frontend" "$repoRoot\deploy" ${REMOTE}:/tmp/

if ($LASTEXITCODE -ne 0) {
    Write-Host "SCP failed. Check SSH access (e.g. ssh $REMOTE)" -ForegroundColor Red
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

# Post-deploy: create DB, .env if missing, migrations, start services
Write-Host "Creating DB, running migrations, starting services..." -ForegroundColor Yellow
$postCmd = "sudo DEPLOY_ROOT=$DEPLOY_ROOT bash $DEPLOY_ROOT/deploy/post-deploy.sh"
ssh $REMOTE $postCmd

if ($LASTEXITCODE -ne 0) {
    Write-Host "Post-deploy failed (check DB, .env, migrations)." -ForegroundColor Red
    exit 1
}

Write-Host "=== Deploy done. App: http://185.229.226.37 or https://185.229.226.37:8443 ===" -ForegroundColor Green
