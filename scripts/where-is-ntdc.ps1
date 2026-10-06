# Где на самом деле слушает NTDC. Запуск из каталога проекта:
#   powershell -File .\scripts\where-is-ntdc.ps1

$ErrorActionPreference = "Continue"
Write-Host "=== этот ПК ===" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.PrefixOrigin -ne "WellKnown" } |
    ForEach-Object { Write-Host ("  {0,-20} {1}" -f $_.InterfaceAlias, $_.IPAddress) }

Write-Host ""
Write-Host "=== DNS ntdc-dev.bsmuk.ru ===" -ForegroundColor Cyan
nslookup ntdc-dev.bsmuk.ru
Write-Host "Ожидается 10.30.30.30 = этот компьютер (uk-khv-001-nv)." -ForegroundColor Yellow

Write-Host ""
Write-Host "=== кто слушает 80/443/8000/8080 на Windows ===" -ForegroundColor Cyan
netstat -ano | findstr "LISTENING" | findstr ":80 :443 :8000 :8080 :8443"

Write-Host ""
Write-Host "=== podman ps ===" -ForegroundColor Cyan
podman ps -a --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"

Write-Host ""
Write-Host "=== curl ===" -ForegroundColor Cyan
foreach ($url in @(
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:8080/health",
    "http://127.0.0.1/health",
    "http://10.30.30.30:8000/health",
    "http://10.30.30.30/health",
    "https://ntdc-dev.bsmuk.ru/health"
)) {
    $out = & curl.exe -skS -m 3 -o NUL -w "%{http_code}" $url 2>&1
    Write-Host ("  {0,-42} {1}" -f $url, $out)
}

Write-Host ""
Write-Host "Если 127.0.0.1 молчит и 10.30.30.30 молчит — порты Podman не на Windows." -ForegroundColor Yellow
Write-Host "Запустите без контейнеров:  .\scripts\run-windows.ps1"
Write-Host "И PUBLIC_BASE_URL=http://ntdc-dev.bsmuk.ru:8000 в .env"
