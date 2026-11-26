import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _origins(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    def __init__(self) -> None:
        self.db_path = Path(os.getenv("DB_PATH", str(BASE_DIR / "itemdb.sqlite3")))
        self.cors_origins = _origins(
            os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
        )
        self.title = "ItemDataBase — база предметов"


settings = Settings()
