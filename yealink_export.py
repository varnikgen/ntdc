#!/usr/bin/env python3
"""
Экспорт конфигурации телефона Yealink через веб-интерфейс (имитация действий человека).
Работает с двумя вариантами веб-интерфейса:
  * старый (T3X):  tbody#PhoneExportCfgConfig, страницы вида /servlet?m=mod_data&p=...
  * новый (T4X):   блок CFGConfigBlock, SPA вида /#/setting-config

Установка:
    pip install playwright
    playwright install chromium

Запуск:
    python yealink_export.py 10.30.16.10 -u admin -p admin -o ./configs
    python yealink_export.py 10.30.18.55 --show      # с окном браузера (для отладки)
"""
import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

EXPORT_RE = re.compile(r"^\s*(Экспорт|Export)\s*$")


def export_locator(frame):
    """Кнопка «Экспорт» конфигурации: старый UI (PhoneExportCfgConfig) или новый (CFGConfigBlock)."""
    old = frame.locator("#PhoneExportCfgConfig").locator(
        "input[type='button'], input[type='submit'], button, a"
    )
    # CFGConfigBlock может быть записан в любом атрибуте (id, class, name, tag ...)
    new = frame.locator("xpath=//*[@*[contains(., 'CFGConfigBlock')]]").get_by_role("button", name=EXPORT_RE)
    return old.or_(new)


def find(page, factory, timeout=10_000):
    """Ищет видимый элемент во всех фреймах страницы. factory(frame) -> Locator.
    Возвращает Locator или None по таймауту."""
    deadline = time.monotonic() + timeout / 1000
    while True:
        for fr in page.frames:
            try:
                loc = factory(fr)
                if loc.count() and loc.first.is_visible():
                    return loc.first
            except Exception:
                pass
        if time.monotonic() > deadline:
            return None
        page.wait_for_timeout(300)


def login(page, host, user, password):
    page.goto(f"https://{host}/", wait_until="domcontentloaded")
    pwd = page.locator("input[type='password']").first
    pwd.wait_for()
    page.locator("input[type='text']").first.fill(user)
    pwd.fill(password)
    pwd.press("Enter")
    try:
        pwd.wait_for(state="hidden", timeout=5_000)
    except PWTimeout:
        # Enter не сработал — жмём кнопку входа
        btn = page.get_by_role("button", name=re.compile(r"^\s*(Войти|Login|OK|Подтвердить|Confirm)\s*$"))
        if btn.count():
            btn.first.click()
        else:
            page.locator("input[type='submit'], input[type='button']").first.click()
        pwd.wait_for(state="hidden")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)


# --- способы открыть страницу «Конфигурации» -------------------------------------------

def _via_hash(page, host):
    """Новый SPA-интерфейс: меняем hash и перезагружаем страницу."""
    page.evaluate("location.hash = '#/setting-config'")
    page.reload(wait_until="networkidle")


def _via_servlet(page, host):
    """Старый интерфейс: страница открывается обычной ссылкой."""
    page.goto(f"https://{host}/servlet?m=mod_data&p=settings-config&q=load", wait_until="networkidle")


def _via_menu(page, host):
    """Клики по меню: Настройки -> Конфигурации."""
    page.goto(f"https://{host}/", wait_until="networkidle")
    tab = find(page, lambda f: f.get_by_text(re.compile(r"^\s*(Настройки|Settings)\s*$")), 6_000)
    if tab:
        tab.click()
        page.wait_for_timeout(700)
    item = find(page, lambda f: f.get_by_text(re.compile(r"^\s*(Конфигурации|Конфигурация|Configuration)\s*$")), 6_000)
    if item:
        item.click()
        page.wait_for_load_state("networkidle")


def open_config_page(page, host):
    """Открывает страницу конфигурации и возвращает кнопку «Экспорт»."""
    # новый интерфейс после входа имеет адрес вида https://ip/#/...
    new_ui = "#/" in page.url
    attempts = [_via_hash, _via_menu, _via_servlet] if new_ui else [_via_servlet, _via_menu, _via_hash]

    for step in attempts:
        try:
            step(page, host)
        except Exception as e:
            print(f"  ({step.__name__}: {e})", file=sys.stderr)
            continue
        btn = find(page, export_locator, 8_000)
        if btn:
            return btn
    return None


def dump_debug(page, out_dir: Path):
    """Сохраняет информацию для диагностики."""
    page.screenshot(path=str(out_dir / "error.png"), full_page=True)
    print(f"Скриншот ошибки: {out_dir / 'error.png'}", file=sys.stderr)
    print(f"URL страницы: {page.url}", file=sys.stderr)
    (out_dir / "page.html").write_text(page.content(), encoding="utf-8")
    print(f"HTML страницы: {out_dir / 'page.html'}", file=sys.stderr)
    for fr in page.frames:
        blk = fr.locator("#PhoneExportCfgConfig")
        if blk.count():
            (out_dir / "block.html").write_text(blk.first.evaluate("e => e.outerHTML"), encoding="utf-8")
            print(f"HTML блока PhoneExportCfgConfig: {out_dir / 'block.html'}", file=sys.stderr)


SKIP_EXT = (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".map")


def click_export(page, context, btn, host, out_dir: Path) -> Path:
    """Кликает «Экспорт» и сохраняет файл.
    1) обычный путь: событие скачивания в браузере;
    2) запасной: если браузер отклонил ответ телефона (chrome-error), повторяем
       неудавшийся запрос через HTTP-клиент Playwright с теми же cookies сессии."""
    reqs, failed = [], []
    def on_request(r):
        reqs.append(r)

    def on_failed(r):
        failed.append(r)

    page.on("request", on_request)
    page.on("requestfailed", on_failed)
    try:
        try:
            with page.expect_download(timeout=30_000) as dl_info:
                btn.click()
            download = dl_info.value
            target = out_dir / f"{host}_{download.suggested_filename}"
            download.save_as(target)
            return target
        except PWTimeout:
            pass
    finally:
        page.remove_listener("request", on_request)
        page.remove_listener("requestfailed", on_failed)

    # --- запасной путь ---
    print("Скачивание в браузере не началось. Запросы после клика:", file=sys.stderr)
    for r in reqs[-15:]:
        print(f"  {r.method} {r.url} [{r.resource_type}]", file=sys.stderr)
    for r in failed:
        print(f"  FAILED {r.url}: {r.failure}", file=sys.stderr)

    candidates = [r for r in failed if not r.url.lower().split("?")[0].endswith(SKIP_EXT)]
    if not candidates:
        candidates = [r for r in reqs
                      if r.resource_type in ("document", "fetch", "xhr", "other")
                      and not r.url.lower().split("?")[0].endswith(SKIP_EXT)][-1:]
    if not candidates:
        raise RuntimeError("Кнопка нажата, но запрос на скачивание не обнаружен (см. список запросов выше).")

    req = candidates[0]
    print(f"Повторяю запрос напрямую: {req.method} {req.url}", file=sys.stderr)
    resp = context.request.fetch(req)
    if not resp.ok:
        raise RuntimeError(f"Телефон ответил {resp.status} {resp.status_text} на {req.url}")

    cd = resp.headers.get("content-disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?", cd, re.I)
    name = Path(unquote(m.group(1))).name if m else "config.cfg"
    target = out_dir / f"{host}_{name}"
    target.write_bytes(resp.body())
    return target


def export_config(host, user, password, out_dir: Path, headless: bool) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(ignore_https_errors=True, accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(20_000)
        page.on("dialog", lambda d: d.accept())  # alert/confirm от телефона

        try:
            login(page, host, user, password)

            export_btn = open_config_page(page, host)
            if export_btn is None:
                raise RuntimeError(
                    "Не нашёл кнопку «Экспорт» в PhoneExportCfgConfig / CFGConfigBlock. "
                    "Фреймы страницы:\n  " + "\n  ".join(f.url for f in page.frames)
                )

            export_btn.scroll_into_view_if_needed()
            return click_export(page, context, export_btn, host, out_dir)

        except Exception:
            try:
                dump_debug(page, out_dir)
            except Exception:
                pass
            raise
        finally:
            context.close()
            browser.close()


def main():
    ap = argparse.ArgumentParser(description="Экспорт конфига Yealink через веб-интерфейс")
    ap.add_argument("host", help="IP телефона, например 10.30.16.10")
    ap.add_argument("-u", "--user", default="admin")
    ap.add_argument("-p", "--password", default="admin")
    ap.add_argument("-o", "--out", default=".", help="папка для сохранения")
    ap.add_argument("--show", action="store_true", help="показывать окно браузера")
    args = ap.parse_args()

    try:
        path = export_config(args.host, args.user, args.password, Path(args.out), headless=not args.show)
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Сохранено: {path}")


if __name__ == "__main__":
    main()