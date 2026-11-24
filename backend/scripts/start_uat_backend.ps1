<#
.SYNOPSIS
  Starts the MediConnect backend for manual staging UAT against an isolated local database.

.DESCRIPTION
  Safety guarantees (all enforced here, without editing backend/.env):
    - Database: mongodb://127.0.0.1:27017/mediconnect_uat (never the Atlas URI in .env).
    - Stripe: refuses to start unless STRIPE_SECRET_KEY in .env is a test key (sk_test_...).
    - External medical image processing: disabled (AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED=false).
    - Email: SMTP disabled (synthetic accounts are never emailed) unless -EnableEmail is passed.
    - JWT: a dedicated random UAT secret stored in the git-ignored backend/uat.env.
    - AI provider: deterministic engine by default. -AiProvider gemini|openai re-enables a provider
      (both had exhausted quota/credit when this script was written).
  Secrets are never printed.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1
  powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1 -SeedOnly
  powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1 -AiProvider gemini
#>
param(
  [ValidateSet('deterministic', 'gemini', 'openai')] [string] $AiProvider = 'deterministic',
  [int] $Port = 8001,
  [string] $BindHost = '127.0.0.1',
  [switch] $SeedOnly,
  [switch] $SkipSeed,
  [switch] $EnableEmail
)
$ErrorActionPreference = 'Stop'
$backend = Split-Path -Parent $PSScriptRoot
Set-Location $backend

function Read-DotEnvValue([string] $file, [string] $name) {
  if (-not (Test-Path $file)) { return '' }
  foreach ($line in Get-Content $file) {
    if ($line -match "^\s*$name\s*=(.*)$") { return $Matches[1].Trim().Trim('"').Trim("'") }
  }
  return ''
}

# Stripe must be test mode.
$stripeKey = Read-DotEnvValue '.env' 'STRIPE_SECRET_KEY'
if (-not $stripeKey.StartsWith('sk_test_')) {
  throw 'Refusing to start UAT: STRIPE_SECRET_KEY in backend/.env is not a Stripe test key (sk_test_...).'
}
$publishable = Read-DotEnvValue '.env' 'STRIPE_PUBLISHABLE_KEY'
if ($publishable -and -not $publishable.StartsWith('pk_test_')) {
  throw 'Refusing to start UAT: STRIPE_PUBLISHABLE_KEY is not a test key (pk_test_...).'
}

# Dedicated UAT JWT secret (git-ignored uat.env).
$uatEnv = Join-Path $backend 'uat.env'
$jwt = Read-DotEnvValue $uatEnv 'UAT_JWT_SECRET'
if (-not $jwt) {
  $bytes = New-Object byte[] 48
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $jwt = [Convert]::ToBase64String($bytes)
  Add-Content -Path $uatEnv -Value "UAT_JWT_SECRET=$jwt"
}

# Isolated environment (process-scoped; backend/.env is not modified).
$env:MONGODB_URI = 'mongodb://127.0.0.1:27017/mediconnect_uat'
$env:DATABASE_NAME = 'mediconnect_uat'
$env:ENVIRONMENT = 'staging'
$env:JWT_SECRET = $jwt
$env:JWT_SECRET_KEY = $jwt
$env:AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED = 'false'
$env:GEMINI_MODEL = 'gemini-flash-latest'   # .env still names the retired gemini-1.5-flash
$env:AI_TIMEOUT_SECONDS = '8'
$env:ALLOWED_ORIGINS = 'http://localhost:5174,http://127.0.0.1:5174'
# A single space is used to blank a value: Windows deletes variables set to '', and python-dotenv would
# then reload the value from .env. The backend strips whitespace, so ' ' means "not configured".
$env:FIREBASE_CREDENTIALS_PATH = ' '
$env:FIREBASE_SERVICE_ACCOUNT_JSON = ' '
if (-not $EnableEmail) { $env:SMTP_HOST = ' ' }
switch ($AiProvider) {
  'deterministic' { $env:GEMINI_API_KEY = ' '; $env:OPENAI_API_KEY = ' ' }
  'openai'        { $env:GEMINI_API_KEY = ' ' }
  'gemini'        { }
}

$python = Join-Path $backend 'venv\Scripts\python.exe'
Write-Host "UAT backend: database=mediconnect_uat (local), AI=$AiProvider, image analysis=disabled, email=$(if ($EnableEmail) {'enabled'} else {'disabled'}), Stripe=test mode"

if (-not $SkipSeed) {
  & $python -m scripts.seed_uat_data
  if ($LASTEXITCODE -ne 0) { throw 'UAT seeding failed.' }
}
if ($SeedOnly) { return }

Write-Host "Starting http://${BindHost}:$Port  (health: /health/ready)"
& $python -m uvicorn app.main:app --host $BindHost --port $Port
