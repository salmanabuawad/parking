# Deploy NEW version to /opt/advancedparking (parking.wavelync.com) on 185.229.226.37.
# The EXISTING /opt/parking deployment is NOT touched.
# Run from repo root: .\deploy\deploy-to-advancedparking.ps1
# Optional flags:
#   -RecreateDb   drop and recreate the 'advancedparking' database
#   -SkipBuild    skip npm/pip install (faster re-deploy if only code changed)

param(
    [switch]$RecreateDb,
    [switch]$SkipBuild
)

$REMOTE      = "root@185.229.226.37"
$DEPLOY_ROOT = "/opt/advancedparking"
$APP_USER    = "advancedparking"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir

Write-Host "=== Deploying to ${REMOTE}:${DEPLOY_ROOT} ===" -ForegroundColor Cyan
Write-Host "    Existing /opt/parking deployment will NOT be touched." -ForegroundColor Yellow

# 1. Copy files to server /tmp
Write-Host "Copying backend, frontend, deploy..." -ForegroundColor Yellow
scp -r "$repoRoot\backend" "$repoRoot\frontend" "$repoRoot\deploy" "${REMOTE}:/tmp/"

if ($LASTEXITCODE -ne 0) {
    Write-Host "SCP failed. Check SSH access: ssh $REMOTE" -ForegroundColor Red
    exit 1
}

# 2. Preserve existing .env, copy files, run setup
Write-Host "Running setup on server..." -ForegroundColor Yellow
$setupCmd = @"
sudo mkdir -p $DEPLOY_ROOT && \
(sudo test -f $DEPLOY_ROOT/backend/.env && sudo cp $DEPLOY_ROOT/backend/.env /tmp/advancedparking.env.bak || true) && \
sudo cp -r /tmp/backend /tmp/frontend /tmp/deploy $DEPLOY_ROOT/ && \
(sudo test -f /tmp/advancedparking.env.bak && sudo mv /tmp/advancedparking.env.bak $DEPLOY_ROOT/backend/.env || true) && \
find $DEPLOY_ROOT/deploy -name '*.sh' -exec sed -i 's/\r//' {} + && \
sudo DEPLOY_ROOT=$DEPLOY_ROOT APP_USER=$APP_USER bash $DEPLOY_ROOT/deploy/setup-advancedparking.sh
"@
ssh $REMOTE $setupCmd

if ($LASTEXITCODE -ne 0) {
    Write-Host "Setup failed." -ForegroundColor Red
    exit 1
}

# 3. Post-deploy: DB, .env, migrations, services
$postScript = "$DEPLOY_ROOT/deploy/post-deploy-advancedparking.sh"
$recreateFlag = if ($RecreateDb) { "RECREATE_DB=1 " } else { "" }
$postCmd = "sed -i 's/\r//' $postScript && sudo ${recreateFlag}DEPLOY_ROOT=$DEPLOY_ROOT APP_USER=$APP_USER bash $postScript"

Write-Host "Running post-deploy (DB + migrations + services)..." -ForegroundColor Yellow
ssh $REMOTE $postCmd

if ($LASTEXITCODE -ne 0) {
    Write-Host "Post-deploy failed. Check DB, .env, and migrations on the server." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Deploy done ===" -ForegroundColor Green
Write-Host "  New:      https://parking.wavelync.com" -ForegroundColor Green
Write-Host "  Existing: http://185.229.226.37 (unchanged)" -ForegroundColor Gray
