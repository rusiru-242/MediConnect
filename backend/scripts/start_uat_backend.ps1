<#
.SYNOPSIS
  Starts the MediConnect backend for manual staging UAT against an isolated local database.

.DESCRIPTION
  Safety guarantees (all enforced here, without editing backend/.env):
    - Database: mongodb://127.0.0.1:27017/mediconnect_uat (never the Atlas URI in .env).
    - Stripe: refuses to start unless STRIPE_SECRET_KEY in .env is a test key (sk_test_...).
    - External medical image processing: disabled (AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED=false) unless
      -EnableVision is passed (A01: synthetic packaging images only, with owner authorization).
    - Email: SMTP disabled (synthetic accounts are never emailed) unless -EnableEmail is passed.
    - Push: Firebase disabled unless -EnablePush is passed with FIREBASE_CREDENTIALS_PATH pointing to a UAT-only
      service-account file kept outside the repository (A02). Twilio SMS is always disabled in UAT.
    - JWT: a dedicated random UAT secret stored in the git-ignored backend/uat.env.
    - AI provider: deterministic engine by default. -AiProvider gemini|openai|both enables providers
      (both = Gemini primary, OpenAI secondary). Live calls are capped by -AiDailyLimit (default 150), counted
      in MongoDB by the provider gateway. Models: gemini-3.8-flash and gpt-6-luna (A01, checked 2026-11-26).
  Secrets are never printed.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1
  powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1 -SeedOnly
  powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1 -AiProvider gemini
  powershell -ExecutionPolicy Bypass -File backend/scripts/start_uat_backend.ps1 -AiProvider both -EnableVision -SkipSeed
#>
param(
  [ValidateSet('deterministic', 'gemini', 'openai', 'both')] [string] $AiProvider = 'deterministic',
  [int] $AiDailyLimit = 150,
  [string] $GeminiModel = 'gemini-3.8-flash',
  [switch] $EnableVision,
  [int] $Port = 8001,
  [string] $BindHost = '127.0.0.1',
  [switch] $SeedOnly,
  [switch] $SkipSeed,
  [switch] $EnableEmail,
  [switch] $EnablePush
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

# Dedicated UAT document-encryption key (B8, Phase 05): git-ignored uat.env, never a deployment key.
$docKey = Read-DotEnvValue $uatEnv 'UAT_DOCUMENT_ENCRYPTION_KEYS'
if (-not $docKey) {
  $kb = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($kb)
  $docKey = 'uat-1:' + [Convert]::ToBase64String($kb)
  Add-Content -Path $uatEnv -Value "UAT_DOCUMENT_ENCRYPTION_KEYS=$docKey"
}
$env:DOCUMENT_ENCRYPTION_KEYS = $docKey

# Isolated environment (process-scoped; backend/.env is not modified).
$env:MONGODB_URI = 'mongodb://127.0.0.1:27017/mediconnect_uat'
$env:DATABASE_NAME = 'mediconnect_uat'
$env:ENVIRONMENT = 'staging'
$env:JWT_SECRET = $jwt
$env:JWT_SECRET_KEY = $jwt
$env:AI_EXTERNAL_IMAGE_ANALYSIS_ENABLED = $(if ($EnableVision) { 'true' } else { 'false' })
# .env still names gemini-1.5-flash (shut down) and gpt-4o-mini (shutdown 2027-01-14); pin the current stable ids.
$env:GEMINI_MODEL = $GeminiModel
$env:OPENAI_MODEL = 'gpt-6-luna'
$env:AI_PRIMARY_PROVIDER = $(if ($AiProvider -eq 'openai') { 'openai' } else { 'gemini' })
$env:AI_SECONDARY_PROVIDER = $(if ($AiProvider -eq 'both') { 'openai' } else { 'none' })
$env:AI_DAILY_REQUEST_LIMIT = "$AiDailyLimit"
$env:AI_TIMEOUT_SECONDS = '12'
$env:AI_VISION_TIMEOUT_SECONDS = '30'
$env:ALLOWED_ORIGINS = 'http://localhost:5174,http://127.0.0.1:5174'
# A single space is used to blank a value: Windows deletes variables set to '', and python-dotenv would
# then reload the value from .env. The backend strips whitespace, so ' ' means "not configured".
if (-not $EnablePush) {
  $env:FIREBASE_CREDENTIALS_PATH = ' '
  $env:FIREBASE_SERVICE_ACCOUNT_JSON = ' '
}
# SMS is never sent from UAT (synthetic phone numbers).
$env:TWILIO_ACCOUNT_SID = ' '
$env:TWILIO_AUTH_TOKEN = ' '
$env:TWILIO_MESSAGING_SERVICE_SID = ' '
if (-not $EnableEmail) { $env:SMTP_HOST = ' ' }
switch ($AiProvider) {
  'deterministic' { $env:GEMINI_API_KEY = ' '; $env:OPENAI_API_KEY = ' ' }
  'openai'        { $env:GEMINI_API_KEY = ' ' }
  'gemini'        { $env:OPENAI_API_KEY = ' ' }
  'both'          { }
}

$python = Join-Path $backend 'venv\Scripts\python.exe'
Write-Host "UAT backend: database=mediconnect_uat (local), documents=encrypted, AI=$AiProvider, image analysis=$(if ($EnableVision) {'enabled'} else {'disabled'}), AI daily limit=$AiDailyLimit, email=$(if ($EnableEmail) {'enabled'} else {'disabled'}), push=$(if ($EnablePush) {'enabled'} else {'disabled'}), sms=disabled, Stripe=test mode"

if (-not $SkipSeed) {
  & $python -m scripts.seed_uat_data
  if ($LASTEXITCODE -ne 0) { throw 'UAT seeding failed.' }
}
if ($SeedOnly) { return }

Write-Host "Starting http://${BindHost}:$Port  (health: /health/ready)"
& $python -m uvicorn app.main:app --host $BindHost --port $Port
