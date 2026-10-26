from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env_file() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT))


@dataclass(frozen=True)
class Settings:
    token: str
    order_url: str
    baraholka_url: str
    ios_url: str
    android_url: str
    manager_username: str
    manager_chat_id: str
    forum_chat_id: str
    cny_usdt_rate: Decimal
    example_product_image: Path
    order_counter: Path
    forum_threads: Path
    message_links: Path
    log_level: str

    @property
    def api_url(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"


settings = Settings(
    token=os.getenv("BOT_TOKEN", "").strip(),
    order_url=os.getenv("ORDER_URL", "").strip(),
    baraholka_url=os.getenv("BARAHOLKA_URL", "").strip(),
    ios_url=os.getenv("IOS_URL", "").strip(),
    android_url=os.getenv("ANDROID_URL", "").strip(),
    manager_username=os.getenv("MANAGER_USERNAME", "").strip().lstrip("@"),
    manager_chat_id=os.getenv("MANAGER_CHAT_ID", "@yeahhha31").strip(),
    forum_chat_id=os.getenv("FORUM_CHAT_ID", "-1003904305474").strip(),
    cny_usdt_rate=Decimal(os.getenv("CNY_USDT_RATE", "0.183")),
    example_product_image=Path(os.getenv("EXAMPLE_PRODUCT_IMAGE", ROOT / "IMG_2905.PNG")),
    order_counter=DATA_DIR / "order_counter.txt",
    forum_threads=DATA_DIR / "forum_threads.json",
    message_links=DATA_DIR / "message_links.json",
    log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
)

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("china-fairy-tale")
