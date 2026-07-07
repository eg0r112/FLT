$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Install Docker Desktop first."
    exit 1
}

Write-Host "Starting PostgreSQL (flt-postgres)..."
docker compose up -d postgres

Write-Host "Waiting for database..."
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    $health = docker inspect --format='{{.State.Health.Status}}' flt-postgres 2>$null
    if ($health -eq "healthy") { $ok = $true; break }
    Start-Sleep -Seconds 1
}

if ($ok) {
    Write-Host "OK: postgresql://garden:garden@127.0.0.1:5432/garden"
} else {
    Write-Host "Container started; wait a few seconds before run.py"
}
