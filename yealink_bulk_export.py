#!/usr/bin/env python3
"""Массовый экспорт конфигов Yealink. Пишет index.json для импорта в NCDC.

Примеры:
  python yealink_bulk_export.py 10.30.18.0/24 -u admin -p admin -o ./configs
  python yealink_bulk_export.py 10.30.18.55,10.30.18.56 -u admin -p admin
  python yealink_bulk_export.py hosts.txt -u admin -p admin
"""
import argparse
import ipaddress
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from yealink_export import export_config  # логика входа/экспорта


def expand_hosts(spec: str) -> list:
    spec = spec.strip()
    if "/" in spec:
        return [str(ip) for ip in ipaddress.ip_network(spec, strict=False).hosts()]
    if "," in spec:
        return [h.strip() for h in spec.split(",") if h.strip()]
    p = Path(spec)
    if p.is_file():
        # utf-8-sig — на случай BOM у файлов, сохранённых в Блокноте Windows
        return [ln.strip() for ln in p.read_text(encoding="utf-8-sig").splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
    return [spec]


def tcp_alive(host: str, ports=(443, 80), timeout=1.5):
    """Быстрая проверка без запуска браузера."""
    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return port
        except OSError:
            continue
    return None


def scan(hosts: list, workers: int = 64) -> dict:
    """Параллельная проверка доступности. Возвращает {host: port} в исходном порядке."""
    with ThreadPoolExecutor(max_workers=workers) as ex:
        ports = list(ex.map(tcp_alive, hosts))
    return {h: p for h, p in zip(hosts, ports) if p}


def main():
    ap = argparse.ArgumentParser(description="Массовый экспорт конфигов Yealink")
    ap.add_argument("hosts", help="CIDR, список через запятую или файл со списком")
    ap.add_argument("-u", "--user", default="admin")
    ap.add_argument("-p", "--password", default="admin")
    ap.add_argument("-o", "--out", default="./configs")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--workers", type=int, default=64, help="потоков для проверки доступности")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    hosts = expand_hosts(args.hosts)

    print(f"Всего адресов: {len(hosts)}. Проверяю доступность...")
    alive = scan(hosts, args.workers)
    skipped = len(hosts) - len(alive)
    print(f"Доступно: {len(alive)}, недоступно: {skipped}")

    index = []
    ok = fail = 0
    total = len(alive)

    for i, (host, port) in enumerate(alive.items(), 1):
        entry = {"ts": datetime.now(timezone.utc).isoformat(),
                 "ip": host, "port": port, "mac": None, "model": None,
                 "file": None, "error": None}

        for attempt in range(1, args.retries + 1):
            try:
                path, mac, model = export_config(host, args.user, args.password,
                                                 out_dir, headless=not args.show)
                entry.update(mac=mac, model=model, file=path.name, error=None)
                ok += 1
                print(f"[{i}/{total}] {host} -> {path.name}")
                break
            except Exception as e:
                entry["error"] = str(e).splitlines()[0] if str(e) else repr(e)
                print(f"[{i}/{total}] {host} попытка {attempt}/{args.retries} НЕУДАЧНО: "
                      f"{entry['error']}", file=sys.stderr)
                if attempt < args.retries:
                    time.sleep(2)
        else:
            fail += 1

        index.append(entry)
        # index.json перезаписываем каждый шаг — не потеряем прогресс при обрыве
        (out_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nИтог: успешно {ok}, ошибок {fail}, пропущено (недоступны) {skipped}")
    print(f"Файлы и index.json: {out_dir.resolve()}")
    if fail:
        print(f"Диагностика неудачных хостов: {(out_dir / 'debug').resolve()}")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
