from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings, resolve_database_url


def main() -> None:
    url = resolve_database_url(settings)
    engine = create_engine(url, connect_args={"connect_timeout": 5}, pool_pre_ping=True)

    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        print("DB OK")
    except Exception as e:
        print("DB FAIL:", type(e).__name__)
        print(str(e))


if __name__ == "__main__":
    main()
