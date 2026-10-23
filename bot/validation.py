from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request


def check_product_link(raw_link: str) -> tuple[bool, str]:
    link = raw_link.strip()
    parsed = urllib.parse.urlparse(link)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or any(char.isspace() for char in link):
        return False, "Отправьте полную ссылку, начинающуюся с http:// или https://."
    headers = {"User-Agent": "Mozilla/5.0 (compatible; YeahmarketBot/1.0)"}
    try:
        with urllib.request.urlopen(urllib.request.Request(link, headers=headers, method="HEAD"), timeout=8) as response:
            status = response.status
        if status in {404, 410} or status >= 500:
            return False, f"Ссылка недоступна: сервер вернул код {status}."
        return True, ""
    except urllib.error.HTTPError as exc:
        if exc.code in {403, 405, 429}:
            return True, ""
        if exc.code in {404, 410} or exc.code >= 500:
            return False, f"Ссылка недоступна: сервер вернул код {exc.code}."
    except (urllib.error.URLError, TimeoutError, OSError):
        return False, "Не удалось открыть ссылку. Проверьте интернет и отправьте рабочую ссылку ещё раз."
    return True, ""
