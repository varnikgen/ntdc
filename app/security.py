"""Общие security-хелперы: MAC, сравнение паролей, кавычки в Yealink cfg, rate-limit."""

from __future__ import annotations

import hmac
import re
import secrets
from collections import defaultdict
from threading import Lock
from time import time

# MAC без разделителей — так он лежит в БД и в имени {MAC}.cfg
MAC_RE = re.compile(r"^[0-9A-Fa-f]{12}$")

# Нельзя предварительно вырезать пробелы из всего User-Agent:
# "Yealink SIP-T46U 108.87.14.1 24:9a:d8:6e:9d:88" иначе склеится
# firmware "...14.1" и MAC "24:..." → "124:9a:...".
MAC_IN_TEXT_RE = re.compile(
    r"(?:^|[\s])(([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2})(?:\s|$)",
    re.IGNORECASE,
)
# Часть прошивок шлёт MAC последним токеном без двоеточий
MAC_BARE_RE = re.compile(r"(?:^|[\s])([0-9A-Fa-f]{12})(?:\s|$)")


def normalize_mac(value: str | None) -> str | None:
    """Приводит MAC к 12 hex-символам UPPERCASE. Иначе None."""
    if not value:
        return None
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", value)
    if len(cleaned) == 12:
        return cleaned.upper()
    return None


def extract_mac(user_agent: str = "", query_mac: str = "") -> str | None:
    """Достаёт MAC из ?mac= (приоритет) или из Yealink User-Agent."""
    mac = normalize_mac(query_mac)
    if mac:
        return mac

    ua = user_agent or ""
    match = MAC_IN_TEXT_RE.search(ua)
    if match:
        return normalize_mac(match.group(1))

    match = MAC_BARE_RE.search(ua)
    if match:
        return normalize_mac(match.group(1))
    return None


# Типичные Yealink User-Agent:
#   "Yealink SIP-T46U 108.87.14.1 24:9a:d8:6e:9d:88"
#   "Yealink SIP-T54W 96.86.0.74"
#   "Yealink VP-T49G ..."
#   "Yealink W70B ..."
# Регекс берёт токен после SIP- / VP- / W и до пробела/конца.
MODEL_FROM_UA_RE = re.compile(
    r"(?:SIP|VP|W)[- ]?([A-Za-z0-9][A-Za-z0-9\-]{1,12})",
    re.IGNORECASE,
)

# Известные популярные модели (для приоритета и нормализации регистра).
# Можно расширять без правки логики.
KNOWN_MODELS = frozenset({
    "T19P", "T21P", "T23G", "T27G", "T29G",
    "T30", "T31", "T31G", "T31P", "T33G", "T33P",
    "T40G", "T40P", "T41S", "T42S", "T42U", "T43U", "T44U", "T46S", "T46U", "T48S", "T48U",
    "T52S", "T53", "T53W", "T54S", "T54W", "T57W", "T58", "T58W", "T58A",
    "T73W", "T74W", "T75W", "T77U", "T80", "T85W", "T87W", "T88V", "T88W",
    "VP59", "VP-T49G", "CP920", "CP925", "CP960", "CP965",
    "W70B", "W73B", "W73P", "W76B", "W78B", "W79P", "W80B", "W90B",
    "WH62", "WH63", "WH66", "WH67",
})


def detect_model_from_ua(user_agent: str = "") -> str | None:
    """Извлекает имя модели Yealink из User-Agent.

    Возвращает UPPERCASE имя (как в $PN) или None.
    Сначала ищет известные модели целиком, затем общий регекс.
    """
    if not user_agent:
        return None
    ua = user_agent.strip()
    ua_upper = ua.upper()

    # Приоритет известным моделям (длинные сначала, чтобы T46U не перебило T46)
    for model in sorted(KNOWN_MODELS, key=len, reverse=True):
        if model.upper() in ua_upper:
            return model.upper()

    m = MODEL_FROM_UA_RE.search(ua)
    if m:
        return m.group(1).upper()
    return None


def quote_cfg(value) -> str:
    """Значение для Yealink cfg: `ключ = всё_до_конца_строки`.

    Кавычить можно только если без них парсер срежет значение:
      # и ;  — комментарий до конца строки
      перевод строки
      сама кавычка

    Нельзя кавычить:
      URL с = и & (Action URL, firmware.url)
      LDAP DN с запятыми (ldap.user / ldap.base) — трубка отправит
      кавычки на bind и LDAP ответит invalid credentials
      ldap.name_attr = cn sn  — пробел здесь нормален
    Булево пишем как 0/1.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value)
    if text == "":
        return ""
    if any(ch in text for ch in '#;"\n\r'):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def constant_time_equals(left: str, right: str) -> bool:
    """Сравнение без раннего выхода — против timing-атак на Basic Auth."""
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


class LoginThrottle:
    """In-memory lockout по IP. На несколько воркеров uvicorn не шарится — этого хватает для одной админки."""

    def __init__(self, max_failures: int, lockout_seconds: int):
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_locked(self, ip: str) -> bool:
        with self._lock:
            self._prune(ip)
            return len(self._hits[ip]) >= self.max_failures

    def record_failure(self, ip: str) -> None:
        with self._lock:
            self._hits[ip].append(time())
            self._prune(ip)

    def record_success(self, ip: str) -> None:
        with self._lock:
            self._hits.pop(ip, None)

    def _prune(self, ip: str) -> None:
        cutoff = time() - self.lockout_seconds
        self._hits[ip] = [t for t in self._hits[ip] if t >= cutoff]
        if not self._hits[ip]:
            self._hits.pop(ip, None)
