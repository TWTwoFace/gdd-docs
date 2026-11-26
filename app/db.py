import json
from collections.abc import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import settings

settings.db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    json_serializer=lambda value: json.dumps(value, ensure_ascii=False),
)


def _casefold(value) -> str:
    return value.casefold() if isinstance(value, str) else ""


@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, _connection) -> None:
    dbapi_connection.create_function("casefold", 1, _casefold, deterministic=True)
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "items" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("items")}
        if "data" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE items ADD COLUMN data TEXT DEFAULT '{}'")
                )


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
