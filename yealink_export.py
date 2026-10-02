#!/usr/bin/env python3
"""
Экспорт конфигурации телефона Yealink через веб-интерфейс (имитация действий человека).

Установка:
    pip install playwright
    playwright install chromium

Запуск:
    python yealink_export.py 10.30.18.55 -u admin -p admin -o ./configs
    python yealink_export.py 10.30.18.55 --show      # с видимым окном браузера (для отладки)
"""
import argparse
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


def export_config(host: str, user: str, password: str, out_dir: Path, headless: bool, nth=None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        # у телефонов самоподписанный сертификат -> игнорируем ошибки HTTPS
        context = browser.new_context(ignore_https_errors=True, accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(20_000)

        try:
            # 1. Авторизация
            page.goto(f"https://{host}/", wait_until="domcontentloaded")

            pwd_input = page.locator("input[type='password']").first
            pwd_input.wait_for()
            user_input = page.locator("input[type='text']").first
            user_input.fill(user)
            pwd_input.fill(password)
            pwd_input.press("Enter")

            # ждём, пока форма логина исчезнет
            pwd_input.wait_for(state="detached")

            # ждём, пока SPA полностью загрузится после входа (появится боковое меню)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1500)

            # 2. Переход на страницу конфигурации.
            # goto на тот же URL с другим #hash не перезагружает SPA, поэтому
            # меняем hash и перезагружаем страницу, чтобы роутер открыл нужный раздел.
            page.evaluate("location.hash = '#/setting-config'")
            page.reload(wait_until="networkidle")

            # 3. Кнопка «Экспорт» (RU) / «Export» (EN) — ищем по тексту
            all_btns = page.get_by_role("button", name=re.compile(r"^\s*(Экспорт|Export)\s*$"))
            try:
                all_btns.first.wait_for(timeout=8_000)
            except PWTimeout:
                # запасной путь: идём по меню Настройки -> Конфигурация
                page.get_by_text(re.compile(r"^(Настройки|Settings)$")).first.click()
                page.get_by_text(re.compile(r"^(Конфигурация|Configuration)$")).first.click()
                all_btns.first.wait_for()

            count = all_btns.count()
            print(f"Найдено кнопок «Экспорт»: {count}")
            for i in range(count):
                box = all_btns.nth(i).bounding_box()
                print(f"  #{i}: y={box['y']:.0f}" if box else f"  #{i}: не видна")

            if nth is not None:
                # ручной выбор кнопки по номеру (0, 1, 2...)
                export_btn = all_btns.nth(nth)
            else:
                # кнопка «Экспорт» внутри блока CFGConfigBlock
                # (имя может быть в id, class, name или tag — проверяем всё)
                block = page.locator(
                    '[id="CFGConfigBlock" i], [class~="CFGConfigBlock" i], '
                    '[class*="CFGConfigBlock" i], [name="CFGConfigBlock" i], '
                    '[tag="CFGConfigBlock" i]'
                ).first
                try:
                    block.wait_for(state="attached", timeout=8_000)
                except PWTimeout:
                    raise RuntimeError(
                        "Не нашёл блок CFGConfigBlock. Запустите с --nth N, "
                        "выбрав номер кнопки из списка выше."
                    )
                export_btn = block.get_by_role(
                    "button", name=re.compile(r"^\s*(Экспорт|Export)\s*$")
                ).last

            export_btn.scroll_into_view_if_needed()

            # 4. Клик + перехват скачивания
            with page.expect_download(timeout=60_000) as dl_info:
                export_btn.click()
            download = dl_info.value

            target = out_dir / f"{host}_{download.suggested_filename}"
            download.save_as(target)
            return target

        except PWTimeout as e:
            page.screenshot(path=str(out_dir / "error.png"))
            raise RuntimeError(f"Таймаут: {e}. Скриншот: {out_dir / 'error.png'}") from e
        finally:
            context.close()
            browser.close()


def main():
    ap = argparse.ArgumentParser(description="Экспорт конфига Yealink через веб-интерфейс")
    ap.add_argument("host", help="IP телефона, например 10.30.18.55")
    ap.add_argument("-u", "--user", default="admin")
    ap.add_argument("-p", "--password", default="admin")
    ap.add_argument("-o", "--out", default=".", help="папка для сохранения")
    ap.add_argument("--show", action="store_true", help="показывать окно браузера")
    ap.add_argument("--nth", type=int, default=None, help="номер кнопки «Экспорт» (с 0), если автоопределение ошиблось")
    args = ap.parse_args()

    try:
        path = export_config(args.host, args.user, args.password, Path(args.out), headless=not args.show, nth=args.nth)
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Сохранено: {path}")


if __name__ == "__main__":
    main()
