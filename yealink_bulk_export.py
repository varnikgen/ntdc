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
import re
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from yealink_export import export_config  # переиспользуем вашу логику логина/экспорта

MAC_IN_NAME_RE = re.compile(r"(?<![0-9A-Fa-f.:])([0-9A-Fa-f]{12})(?![0-9A-Fa-f])")


def expand_hosts(spec: str) -> list:
    spec = spec.strip()
    if "/" in spec:
        return [str(ip) for ip in ipaddress.ip_network(spec, strict=False).hosts()]
    if "," in spec:
        return [h.strip() for h in spec.split(",") if h.strip()]
    p = Path(spec)
    if p.is_file():
        return [ln.strip() for ln in p.read_text().splitlines()
                if ln.strip() and not ln.startswith("#")]
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


def mac_from_filename(name: str):
    m = MAC_IN_NAME_RE.search(name)
    return m.group(1).upper() if m else None


def main():
    ap = argparse.ArgumentParser(description="Массовый экспорт конфигов Yealink")
    ap.add_argument("hosts", help="CIDR, список через запятую или файл со списком")
    ap.add_argument("-u", "--user", default="admin")
    ap.add_argument("-p", "--password", default="admin")
    ap.add_argument("-o", "--out", default="./configs")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    hosts = expand_hosts(args.hosts)
    index = []
    ok = fail = skipped = 0

    print(f"Всего адресов: {len(hosts)}")
    for i, host in enumerate(hosts, 1):
        port = tcp_alive(host)
        if not port:
            skipped += 1
            continue  # мёртвый адрес — не тратим время на браузер

        entry = {"ts": datetime.now(timezone.utc).isoformat(),
                 "ip": host, "port": port, "mac": None, "file": None, "error": None}
        for attempt in range(1, args.retries + 1):
            try:
                path = export_config(host, args.user, args.password,
                                     out_dir, headless=not args.show)
                entry["mac"] = mac_from_filename(path.name)
                entry["file"] = path.name
                ok += 1
                print(f"[{i}/{len(hosts)}] {host} -> {path.name} (MAC: {entry['mac']})")
                break
            except Exception as e:
                entry["error"] = str(e)
                print(f"[{i}/{len(hosts)}] {host} попытка {attempt} НЕУДАЧНО: {e}",
                      file=sys.stderr)
                time.sleep(2)
        else:
            fail += 1

        index.append(entry)
        # index.json перезаписываем каждый шаг — не потеряем прогресс при обрыве
        (out_dir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nИтог: успешно {ok}, ошибок {fail}, пропущено (недоступны) {skipped}")
    print(f"Файлы и index.json: {out_dir.resolve()}")


if __name__ == "__main__":
    main()