from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote_plus
from typing import Any

from sqlalchemy import MetaData, create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql.sqltypes import Boolean, DateTime, Float, Integer, Numeric, Text


DEFAULT_SQLITE_URL = "sqlite:///data/bili.db"
TARGET_PG_HOST = "127.0.0.1"
TARGET_PG_PORT = 5432
TARGET_PG_USER = "postgres"
TARGET_PG_PASSWORD = "123456"
TARGET_PG_DATABASE = "bili_flow"


def build_default_postgres_url() -> str:
    if TARGET_PG_PASSWORD:
        auth = f"{TARGET_PG_USER}:{quote_plus(TARGET_PG_PASSWORD)}"
    else:
        auth = TARGET_PG_USER
    return f"postgresql+psycopg://{auth}@{TARGET_PG_HOST}:{TARGET_PG_PORT}/{TARGET_PG_DATABASE}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate bili-flow data from SQLite to PostgreSQL.",
    )
    parser.add_argument(
        "--sqlite-url",
        default=DEFAULT_SQLITE_URL,
        help=f"Source SQLite URL. Default: {DEFAULT_SQLITE_URL}",
    )
    parser.add_argument(
        "--postgres-url",
        default=build_default_postgres_url(),
        help=(
            "Target PostgreSQL URL. "
            f"Default: {build_default_postgres_url()} "
            "(edit TARGET_PG_PASSWORD in this script if needed)"
        ),
    )
    parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="Delete target table data before importing.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Batch insert size. Default: 500",
    )
    parser.add_argument(
        "--skip-missing-source-tables",
        action="store_true",
        help="Skip tables that do not exist in the SQLite source. Default: enabled.",
    )
    parser.set_defaults(skip_missing_source_tables=True)
    return parser.parse_args()


def ensure_sqlite_file_exists(sqlite_url: str) -> None:
    if not sqlite_url.startswith("sqlite:///"):
        return
    db_path = Path(sqlite_url.replace("sqlite:///", "", 1))
    if not db_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")


def build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return create_engine(url, future=True)
    return create_engine(url, future=True, pool_pre_ping=True)


def reflect_source_metadata(engine: Engine) -> MetaData:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    return metadata


def quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def fetch_runtime_sqlite_types(source_engine: Engine, table_name: str, column_name: str) -> set[str]:
    sql = (
        f"SELECT DISTINCT typeof({quote_ident(column_name)}) "
        f"FROM {quote_ident(table_name)} "
        f"WHERE {quote_ident(column_name)} IS NOT NULL"
    )
    with source_engine.connect() as conn:
        rows = conn.exec_driver_sql(sql).fetchall()
    return {str(row[0]).lower() for row in rows if row[0] is not None}


def coerce_target_type(column, runtime_types: set[str]):
    generic_type = column.type
    if isinstance(generic_type, DateTime):
        return generic_type
    if "text" not in runtime_types:
        return generic_type
    if isinstance(generic_type, (Integer, Boolean, Float, Numeric)):
        return Text()
    return generic_type


def is_integer_like_type(column) -> bool:
    return isinstance(column.type, Integer)


def build_target_metadata_from_source(source_metadata: MetaData, source_engine: Engine) -> MetaData:
    target_metadata = MetaData()
    for table in source_metadata.sorted_tables:
        cloned_table = table.to_metadata(target_metadata)
        for column in cloned_table.columns:
            try:
                column.type = column.type.as_generic()
            except Exception:
                pass
            runtime_types = fetch_runtime_sqlite_types(source_engine, table.name, column.name)
            column.type = coerce_target_type(column, runtime_types)
            column.default = None
            column.server_default = None
    return target_metadata


def normalize_value(value: Any) -> Any:
    if isinstance(value, memoryview):
        return bytes(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        normalized[key] = normalize_value(value)
    return normalized


def chunked(iterable: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [iterable[idx : idx + size] for idx in range(0, len(iterable), size)]


def reset_postgres_sequence(conn, table_name: str) -> None:
    conn.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence(:table_name, 'id'),
                COALESCE((SELECT MAX(id) FROM {}), 1),
                COALESCE((SELECT MAX(id) FROM {}) IS NOT NULL, false)
            )
            """.format(table_name, table_name)
        ),
        {"table_name": table_name},
    )


def copy_table(
    source_engine: Engine,
    target_engine: Engine,
    source_metadata: MetaData,
    target_metadata: MetaData,
    table_name: str,
    *,
    truncate_target: bool,
    chunk_size: int,
    skip_missing_source_tables: bool,
) -> int:
    source_table = source_metadata.tables.get(table_name)
    if source_table is None:
        if skip_missing_source_tables:
            print(f"[skip] source table missing: {table_name}")
            return 0
        raise RuntimeError(f"Source table missing: {table_name}")

    target_table = target_metadata.tables.get(table_name)
    if target_table is None:
        raise RuntimeError(f"Target table missing: {table_name}")
    target_columns = [column.name for column in source_table.columns]

    if not target_columns:
        print(f"[skip] no common columns: {table_name}")
        return 0

    total_inserted = 0

    with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
        if truncate_target:
            target_conn.execute(target_table.delete())

        result = source_conn.execute(select(*[source_table.c[name] for name in target_columns]))
        while True:
            rows = result.fetchmany(chunk_size)
            if not rows:
                break
            payload = [normalize_row(dict(row._mapping)) for row in rows]
            for batch in chunked(payload, chunk_size):
                target_conn.execute(target_table.insert(), batch)
                total_inserted += len(batch)

        if (
            "id" in target_columns
            and target_engine.dialect.name == "postgresql"
            and is_integer_like_type(target_table.c["id"])
        ):
            reset_postgres_sequence(target_conn, table_name)

    print(f"[ok] {table_name}: {total_inserted} rows")
    return total_inserted


def main() -> None:
    args = parse_args()
    ensure_sqlite_file_exists(args.sqlite_url)

    source_engine = build_engine(args.sqlite_url)
    target_engine = build_engine(args.postgres_url)

    if target_engine.dialect.name != "postgresql":
        raise RuntimeError("Target engine must be PostgreSQL")

    if not TARGET_PG_PASSWORD and args.postgres_url == build_default_postgres_url():
        print("[warn] TARGET_PG_PASSWORD is empty; fill it in this script if PostgreSQL requires password auth")

    print(f"[info] source: {args.sqlite_url}")
    print(f"[info] target: {args.postgres_url}")

    source_metadata = reflect_source_metadata(source_engine)
    target_metadata = build_target_metadata_from_source(source_metadata, source_engine)
    source_tables = set(source_metadata.tables.keys())
    target_tables = [table.name for table in source_metadata.sorted_tables]

    print("[info] creating target schema from SQLite source metadata")
    target_metadata.create_all(target_engine)

    print(f"[info] source tables: {len(source_tables)}")
    print(f"[info] target tables: {len(target_tables)}")

    total_rows = 0
    for table_name in target_tables:
        inserted = copy_table(
            source_engine,
            target_engine,
            source_metadata,
            target_metadata,
            table_name,
            truncate_target=args.truncate_target,
            chunk_size=args.chunk_size,
            skip_missing_source_tables=args.skip_missing_source_tables,
        )
        total_rows += inserted

    print(f"[done] migrated rows: {total_rows}")
    print(f"[done] finished at {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    main()
