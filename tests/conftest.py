import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DB_PATH"] = str(ROOT / "test_itemdb.sqlite3")
os.environ["CORS_ORIGINS"] = "http://testserver"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import Base, engine
from app.main import app
from app.template import seed_template


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))
    seed_template()
    yield
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))
    seed_template()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
