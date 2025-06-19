"""Database helpers for the conciliations Streamlit app.

There are two PostgreSQL databases involved:
1. *Transactions DB* (env vars prefixed with **DB_***).  Contains the
   `transactions`, `transaction` and `comun_transaction` tables that we
   need to read and update.
2. *Organizations DB* (env vars prefixed with **ORG_DB_***).  Contains the
   `organizations` table that maps `organization_id -> name`.

Both connections are created on‑demand and kept in an in‑memory cache so
we reuse them across Streamlit reruns.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import os
from typing import Any, Dict, List, Tuple

import pandas as pd
import psycopg2
import psycopg2.extras as extras

###############################################################################
# Low‑level helpers
###############################################################################

def _get_conn_params(prefix: str) -> Dict[str, Any]:
    """Return a dict with psycopg2.connect(**params) parameters."""
    keys = ["HOST", "PORT", "NAME", "USER", "PASSWORD"]
    return {
        k.lower(): os.getenv(f"{prefix}_{k}")
        for k in keys
    }

@lru_cache(maxsize=2)
def _connection(prefix: str):
    """Lazily create and cache a psycopg2 connection for *prefix* env vars."""
    params = _get_conn_params(prefix)
    if not params["host"]:
        raise RuntimeError(f"Missing env vars for {prefix}_… database configuration")
    conn = psycopg2.connect(cursor_factory=extras.RealDictCursor, **params)
    conn.autocommit = True  # we handle commits manually where required
    return conn

@contextmanager
def get_cursor(prefix: str):
    """Context manager that yields a cursor and commits/rolls back properly."""
    conn = _connection(prefix)
    cur = conn.cursor()
    try:
        yield cur
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        cur.close()

###############################################################################
# Public API
###############################################################################

def fetch_transactions(
    date_from: str | None = None,
    date_to: str | None = None,
    product_accounts: List[str] | None = None,
    description_search: str | None = None,
    organization_names: List[str] | None = None,
) -> pd.DataFrame:
    """Return a DataFrame of transactions filtered by the supplied criteria."""
    wheres: List[str] = []
    params: List[Any] = []

    if date_from and date_to:
        wheres.append("transaction_date BETWEEN %s AND %s")
        params.extend([date_from, date_to])
    elif date_from:
        wheres.append("transaction_date >= %s")
        params.append(date_from)
    elif date_to:
        wheres.append("transaction_date <= %s")
        params.append(date_to)

    if product_accounts:
        placeholders = ",".join(["%s"] * len(product_accounts))
        wheres.append(f"product_account IN ({placeholders})")
        params.extend(product_accounts)

    if description_search:
        wheres.append("description ILIKE %s")
        params.append(f"%{description_search}%")

    # First query the basic transaction info ---------------------------------
    base_query = """
        SELECT id_transactionai,
               transaction_date,
               product_account,
               amount,
               balance,
               description,
               organization_id,
               conciliation
        FROM transactions
    """
    if wheres:
        base_query += " WHERE " + " AND ".join(wheres)
    base_query += " ORDER BY transaction_date DESC LIMIT 5000"  # safety guard

    with get_cursor("DB") as cur:
        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    # ------------------------------------------------------------------------
    # Enrich with organization names (2nd database)
    # ------------------------------------------------------------------------
    org_ids = df["organization_id"].dropna().unique().tolist()

    if organization_names is not None:
        # Map names to ids first so we can filter afterwards
        name_to_id = _organization_name_to_id()
        allowed_ids = [name_to_id[n] for n in organization_names if n in name_to_id]
        df = df[df["organization_id"].isin(allowed_ids)]
        org_ids = allowed_ids  # reduce the set we need to fetch

    if org_ids:
        id_to_name = _organization_id_to_name(org_ids)
        df["organization_name"] = df["organization_id"].map(id_to_name)
    else:
        df["organization_name"] = None

    return df

# ---------------------------------------------------------------------------
# Distinct values helpers (used to populate filter widgets)
# ---------------------------------------------------------------------------

def distinct_product_accounts() -> List[str]:
    with get_cursor("DB") as cur:
        cur.execute("SELECT DISTINCT product_account FROM transactions ORDER BY 1")
        return [r[0] for r in cur.fetchall() if r[0]]

def distinct_organization_names() -> List[str]:
    with get_cursor("ORG_DB") as cur:
        cur.execute("SELECT DISTINCT name FROM organizations ORDER BY 1")
        return [r[0] for r in cur.fetchall() if r[0]]

# ---------------------------------------------------------------------------
# Update helpers
# ---------------------------------------------------------------------------

def update_conciliation(transaction_ids: List[int], status: str) -> None:
    """Bulk‑update the conciliation status of *transaction_ids*.

    *status* must be either "CONCILIATED" or "NOT_CONCILIATED".
    """
    if status not in {"CONCILIATED", "NOT_CONCILIATED"}:
        raise ValueError("status must be 'CONCILIATED' or 'NOT_CONCILIATED'")

    if not transaction_ids:
        return

    # Prepare bulk update ----------------------------------------------------
    placeholders = ",".join(["%s"] * len(transaction_ids))

    with get_cursor("DB") as cur:
        # 1. Table `transaction` (singular)
        cur.execute(
            f"UPDATE transaction SET conciliation = %s WHERE id_transactionai IN ({placeholders})",
            (status, *transaction_ids),
        )
        # 2. Table `comun_transaction`
        cur.execute(
            f"UPDATE comun_transaction SET conciliation = %s, conciliation_status = %s WHERE id_transaction IN ({placeholders})",
            (status, status, *transaction_ids),
        )

###############################################################################
# Internal helpers for organizations DB
###############################################################################

def _organization_id_to_name(ids: List[int]) -> Dict[int, str]:
    placeholders = ",".join(["%s"] * len(ids))
    query = f"SELECT organization_id, name FROM organizations WHERE organization_id IN ({placeholders})"
    with get_cursor("ORG_DB") as cur:
        cur.execute(query, tuple(ids))
        return {row[0]: row[1] for row in cur.fetchall()}

def _organization_name_to_id() -> Dict[str, int]:
    with get_cursor("ORG_DB") as cur:
        cur.execute("SELECT organization_id, name FROM organizations")
        return {row[1]: row[0] for row in cur.fetchall()}