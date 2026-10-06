# NTDC без Podman: uvicorn слушает Windows-интерфейс 10.30.30.30.
# Podman Desktop/WSL пробрасывает порты только на 127.0.0.1 (и то не всегда),
# с LAN и по DNS ntdc-dev.bsmuk.ru → 10.30.30.30 получается ERR_CONNECTION_REFUSED.
#
# Запуск из корня проекта, venv уже активирован, PowerShell от Администратора
# если нужен порт 80:
#   .\scripts\run-windows.ps1
#   .\scripts\run-windows.ps1 -Port 80

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))

if (-not (Test-Path .env)) {
    Write-Error "Нет .env — скопируйте .env.example и заполните пароли."
}

New-Item -ItemType Directory -Force -Path data | Out-Null

$listen = "http://0.0.0.0:$Port"
Write-Host "NTDC на $listen" -ForegroundColor Cyan
Write-Host "Админка:  http://10.30.30.30:$Port/"
Write-Host "Имя DNS:  http://ntdc-dev.bsmuk.ru:$Port/   (если Port=80 — без :$Port)"
Write-Host "В .env поставьте PUBLIC_BASE_URL=http://ntdc-dev.bsmuk.ru$(if ($Port -ne 80) { ":$Port" })"
Write-Host ""

try {
    New-NetFirewallRule -DisplayName "NTDC $Port" -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -ErrorAction SilentlyContinue | Out-Null
} catch {}

python -m uvicorn app.main:app --host 0.0.0.0 --port $Port --proxy-headers --forwarded-allow-ips "*"
