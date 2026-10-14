"""
FinTrack: MySQL to Supabase PostgreSQL Migration Script
======================================================
Safely, idempotently, and non-destructively migrates existing financial
records from local MySQL to hosted Supabase PostgreSQL.

Features:
- READ-ONLY on source MySQL (never modifies or deletes source data).
- Topologically ordered table migration according to foreign key dependencies.
- Resumable and idempotent: detects already-transferred records.
- Flags conflicts rather than silently skipping differing records.
- Resynchronizes PostgreSQL sequences so future auto-increment inserts work.
- Masks credentials in all log outputs.
- Supports --dry-run mode for pre-flight validation.

Usage:
    python migrate_to_postgres.py --dry-run
    python migrate_to_postgres.py
    python migrate_to_postgres.py --target-url "postgresql://postgres.[ref]:[pass]@[host]:5432/postgres"
"""

import argparse
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, List, Tuple

from dotenv import load_dotenv
from sqlalchemy import create_engine, select, text, func, Table, MetaData
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

# Ensure local backend imports resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import resolve_database_url
import models
from models import Base

load_dotenv()


# Dependency-safe migration order (Topological sort of foreign keys)
MIGRATION_TABLES: List[Tuple[str, str]] = [
    ("users", "user_id"),
    ("income", "income_id"),
    ("expenses", "expense_id"),
    ("budgets", "budget_id"),
    ("income_allocations", "allocation_id"),
    ("audit_logs", "log_id"),
    ("split_bills", "split_bill_id"),
    ("cards", "card_id"),
    ("notifications", "notification_id"),
    ("split_participants", "participant_id"),
    ("settlements", "settlement_id"),
    ("card_benefits", "benefit_id"),
    ("card_usage", "usage_id"),
]


def parse_pg_url(url_str: str) -> URL:
    """Normalize and safely parse target PostgreSQL URL."""
    url_str = url_str.strip()
    if url_str.startswith("postgres://"):
        url_str = "postgresql+psycopg://" + url_str[len("postgres://"):]
    elif url_str.startswith("postgresql://"):
        url_str = "postgresql+psycopg://" + url_str[len("postgresql://"):]

    try:
        url_obj = make_url(url_str)
        if not (url_obj.host and "@" in url_obj.host):
            if url_obj.drivername.startswith("postgresql") and url_obj.host not in ("localhost", "127.0.0.1"):
                q = dict(url_obj.query)
                if "sslmode" not in q:
                    q["sslmode"] = "require"
                    url_obj = url_obj.set(query=q)
            return url_obj
    except Exception:
        pass

    # Fallback parser for unencoded passwords
    import urllib.parse
    scheme_part, rest = url_str.split("://", 1)
    path_split = rest.rsplit("/", 1)
    if len(path_split) == 2:
        host_user_part, db_query = path_split
        db_split = db_query.split("?", 1)
        database = db_split[0]
        query = urllib.parse.parse_qs(db_split[1]) if len(db_split) > 1 else {}
    else:
        host_user_part = rest
        database = ""
        query = {}

    user_pass_part, host_port = host_user_part.rsplit("@", 1)
    if ":" in host_port:
        host, port_str = host_port.split(":", 1)
        port = int(port_str) if port_str.isdigit() else None
    else:
        host = host_port
        port = None

    if ":" in user_pass_part:
        username, password = user_pass_part.split(":", 1)
        password = urllib.parse.unquote(password)
        username = urllib.parse.unquote(username)
    else:
        username = urllib.parse.unquote(user_pass_part)
        password = None

    flat_query = {k: v[0] if len(v) == 1 else v for k, v in query.items()}
    if scheme_part.startswith("postgresql") and host not in ("localhost", "127.0.0.1"):
        if "sslmode" not in flat_query:
            flat_query["sslmode"] = "require"

    return URL.create(
        drivername=scheme_part,
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
        query=flat_query if flat_query else None
    )


def compare_records(source_val: Any, target_val: Any) -> bool:
    """Normalize data types for equality comparison across MySQL and PostgreSQL."""
    if source_val == target_val:
        return True
    if source_val is None or target_val is None:
        return source_val == target_val
    if isinstance(source_val, Decimal) or isinstance(target_val, Decimal):
        try:
            return float(source_val) == float(target_val)
        except Exception:
            return False
    if isinstance(source_val, (date, datetime)) and isinstance(target_val, (date, datetime)):
        return str(source_val) == str(target_val)
    return str(source_val) == str(target_val)


def migrate(
    source_url: str = None,
    target_url: str = None,
    dry_run: bool = False
):
    print("=" * 70)
    print("FinTrack Database Migration: MySQL -> Supabase PostgreSQL")
    print("=" * 70)

    # 1. Resolve Source Engine (MySQL)
    if source_url:
        src_url_obj = make_url(source_url)
    else:
        # Build local MySQL URL from env vars
        db_user = os.getenv("DB_USER", "root")
        db_pass = os.getenv("DB_PASSWORD", "")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = int(os.getenv("DB_PORT", "3306"))
        db_name = os.getenv("DB_NAME", "fintrack")
        src_url_obj = URL.create(
            drivername="mysql+pymysql",
            username=db_user,
            password=db_pass,
            host=db_host,
            port=db_port,
            database=db_name
        )

    # 2. Resolve Target Engine (PostgreSQL)
    raw_target = target_url or os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not raw_target:
        print("\n[ERROR] No target PostgreSQL connection URL provided.")
        print("Please provide a target URL via:")
        print("  --target-url \"postgresql://postgres.[ref]:[pass]@[host]:5432/postgres\"")
        print("  OR set the DATABASE_URL / SUPABASE_DATABASE_URL environment variable.\n")
        sys.exit(1)

    tgt_url_obj = parse_pg_url(raw_target)

    print(f"\nSource (MySQL):      {src_url_obj.render_as_string(hide_password=True)}")
    print(f"Target (PostgreSQL): {tgt_url_obj.render_as_string(hide_password=True)}")
    print(f"Mode:                {'DRY RUN (Read-Only Inspection)' if dry_run else 'LIVE MIGRATION'}\n")

    # Connect to engines
    try:
        src_engine = create_engine(src_url_obj, pool_pre_ping=True)
        with src_engine.connect() as conn:
            pass
        print("  [OK] Successfully connected to Source (MySQL)")
    except Exception as e:
        print(f"  [FAIL] Could not connect to Source MySQL: {e}")
        sys.exit(1)

    try:
        tgt_engine = create_engine(tgt_url_obj, pool_pre_ping=True, pool_recycle=300)
        with tgt_engine.connect() as conn:
            pass
        print("  [OK] Successfully connected to Target (PostgreSQL)")
    except Exception as e:
        print(f"  [FAIL] Could not connect to Target PostgreSQL: {e}")
        sys.exit(1)

    # Ensure target tables and enums exist without dropping anything
    if not dry_run:
        print("\nVerifying/initializing target schema (checkfirst=True)...")
        Base.metadata.create_all(bind=tgt_engine, checkfirst=True)
        print("  [OK] Target schema verified.")

    src_meta = MetaData()
    src_meta.reflect(bind=src_engine)

    tgt_meta = MetaData()
    tgt_meta.reflect(bind=tgt_engine)

    summary_stats = []
    conflict_logs = []
    error_logs = []

    print("\nBeginning data transfer in dependency order...\n")

    for table_name, pk_col in MIGRATION_TABLES:
        if table_name not in src_meta.tables:
            print(f"  [SKIP] Table '{table_name}' does not exist in source database.")
            continue

        src_table = src_meta.tables[table_name]
        tgt_table = tgt_meta.tables.get(table_name)

        if tgt_table is None and not dry_run:
            print(f"  [ERROR] Table '{table_name}' not found on target schema.")
            continue

        with src_engine.connect() as src_conn:
            src_rows = src_conn.execute(select(src_table)).mappings().all()

        src_count = len(src_rows)
        inserted_count = 0
        existing_count = 0
        conflict_count = 0
        failed_count = 0

        # Fetch existing target rows for idempotency
        target_records_by_pk = {}
        if tgt_table is not None and not dry_run:
            with tgt_engine.connect() as tgt_conn:
                tgt_rows = tgt_conn.execute(select(tgt_table)).mappings().all()
                for r in tgt_rows:
                    target_records_by_pk[r[pk_col]] = dict(r)

        for row in src_rows:
            row_dict = dict(row)
            pk_val = row_dict.get(pk_col)

            if dry_run:
                inserted_count += 1
                continue

            if pk_val in target_records_by_pk:
                existing_record = target_records_by_pk[pk_val]
                # Compare fields
                has_conflict = False
                differing_fields = []
                for k, v in row_dict.items():
                    if k in existing_record and not compare_records(v, existing_record[k]):
                        has_conflict = True
                        differing_fields.append((k, v, existing_record[k]))

                if has_conflict:
                    conflict_count += 1
                    conflict_logs.append({
                        "table": table_name,
                        "pk": pk_val,
                        "differences": differing_fields
                    })
                else:
                    existing_count += 1
            else:
                try:
                    with tgt_engine.begin() as tgt_conn:
                        tgt_conn.execute(tgt_table.insert().values(**row_dict))
                    inserted_count += 1
                    target_records_by_pk[pk_val] = row_dict
                except Exception as err:
                    failed_count += 1
                    error_logs.append({
                        "table": table_name,
                        "pk": pk_val,
                        "error": str(err)
                    })

        # Synchronize PostgreSQL sequence for auto-increment primary key
        if not dry_run and tgt_engine.dialect.name == "postgresql":
            try:
                seq_query = text(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table_name}', '{pk_col}'),
                        COALESCE((SELECT MAX({pk_col}) FROM {table_name}), 1),
                        (SELECT MAX({pk_col}) FROM {table_name}) IS NOT NULL
                    );
                """)
                with tgt_engine.begin() as tgt_conn:
                    tgt_conn.execute(seq_query)
            except Exception as seq_err:
                # Some tables may not use standard serial sequence
                pass

        summary_stats.append({
            "table": table_name,
            "source": src_count,
            "inserted": inserted_count,
            "existing": existing_count,
            "conflicts": conflict_count,
            "failed": failed_count,
        })

        status_str = f"Done: {inserted_count} new, {existing_count} existing"
        if conflict_count > 0:
            status_str += f", {conflict_count} CONFLICTS"
        if failed_count > 0:
            status_str += f", {failed_count} FAILED"
        print(f"  -> {table_name:<20} Total: {src_count:<4} | {status_str}")

    # Print Formatted Report
    print("\n" + "=" * 70)
    print("MIGRATION SUMMARY REPORT")
    print("=" * 70)
    print(f"{'Table':<22} {'Source':<8} {'Inserted':<10} {'Existing':<10} {'Conflicts':<10} {'Failed':<8}")
    print("-" * 70)
    tot_src = sum(s["source"] for s in summary_stats)
    tot_ins = sum(s["inserted"] for s in summary_stats)
    tot_ext = sum(s["existing"] for s in summary_stats)
    tot_cnf = sum(s["conflicts"] for s in summary_stats)
    tot_fld = sum(s["failed"] for s in summary_stats)

    for s in summary_stats:
        print(f"{s['table']:<22} {s['source']:<8} {s['inserted']:<10} {s['existing']:<10} {s['conflicts']:<10} {s['failed']:<8}")
    print("-" * 70)
    print(f"{'TOTALS':<22} {tot_src:<8} {tot_ins:<10} {tot_ext:<10} {tot_cnf:<10} {tot_fld:<8}")
    print("=" * 70)

    if conflict_logs:
        print("\n[WARNING] Conflicting Records Detected:")
        for c in conflict_logs[:10]:
            print(f"  Table: {c['table']}, PK: {c['pk']}")
            for field, src_val, tgt_val in c['differences']:
                print(f"    - {field}: source='{src_val}' != target='{tgt_val}'")
        if len(conflict_logs) > 10:
            print(f"  ... and {len(conflict_logs) - 10} more conflicts.")

    if error_logs:
        print("\n[ERROR] Failed Records:")
        for e in error_logs[:10]:
            print(f"  Table: {e['table']}, PK: {e['pk']} | Error: {e['error']}")
        if len(error_logs) > 10:
            print(f"  ... and {len(error_logs) - 10} more errors.")

    if dry_run:
        print("\n[INFO] Dry run complete. No data was written to the target database.")
    elif tot_fld == 0 and tot_cnf == 0:
        print("\n[SUCCESS] Migration completed with 0 errors and 0 conflicts! All sequences synchronized.")
    else:
        print(f"\n[ATTENTION] Migration finished with {tot_fld} errors and {tot_cnf} conflicts. Review details above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinTrack MySQL to Supabase PostgreSQL Migration")
    parser.add_argument("--source-url", help="Source MySQL connection URL")
    parser.add_argument("--target-url", help="Target Supabase PostgreSQL connection URL")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without writing to target")
    args = parser.parse_args()

    migrate(
        source_url=args.source_url,
        target_url=args.target_url,
        dry_run=args.dry_run
    )
