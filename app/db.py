"""Database helpers for the conciliations Streamlit app."""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import os
from typing import Any, Dict, List, Tuple

import pandas as pd
import psycopg2
import psycopg2.extras as extras
from psycopg2.extras import RealDictCursor

###############################################################################
# Low‑level helpers
###############################################################################

def get_connection(prefix: str):
    return psycopg2.connect(
        host=os.getenv(f"{prefix}_HOST"),
        port=os.getenv(f"{prefix}_PORT", 5432),
        dbname=os.getenv(f"{prefix}_NAME"),
        user=os.getenv(f"{prefix}_USER"),
        password=os.getenv(f"{prefix}_PASSWORD"),
        cursor_factory=RealDictCursor,
        connect_timeout=5,
    )

@lru_cache(maxsize=2)
def _connection(prefix: str):
    conn = get_connection(prefix)
    conn.autocommit = True
    return conn

@contextmanager
def get_cursor(prefix: str):
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
    id_transaction: int | None = None,
) -> pd.DataFrame:
    wheres: List[str] = []
    params: List[Any] = []

    # Filtro organizaciones
    wheres.append("tr.id_organizacion IN (1,11,12,13,14)")


    if date_from and date_to:
        wheres.append("tr.date BETWEEN %s AND %s")
        params.extend([date_from, date_to])
    elif date_from:
        wheres.append("tr.date >= %s")
        params.append(date_from)
    elif date_to:
        wheres.append("tr.date <= %s")
        params.append(date_to)

    if product_accounts:
        placeholders = ",".join(["%s"] * len(product_accounts))
        wheres.append(f"tr.product_account IN ({placeholders})")
        params.extend(product_accounts)

    if description_search:
        wheres.append("tr.description ILIKE %s")
        params.append(f"%{description_search}%")

    if id_transaction:
        wheres.append("tr.id_transactionai = %s")
        params.append(id_transaction)

    if organization_names:
        name_to_id = _organization_name_to_id()
        allowed_ids = [name_to_id[n] for n in organization_names if n in name_to_id]
        if allowed_ids:
            placeholders = ",".join(["%s"] * len(allowed_ids))
            wheres.append(f"tr.id_organizacion IN ({placeholders})")
            params.extend(allowed_ids)

    base_query = """
        SELECT tr.id_transactionai,
               tr.date,
               tr.product_account,
               tr.amount,
               tr.balance,
               tr.description,
               tr.id_organizacion,
               ct.conciliation
        FROM transaction tr
        LEFT JOIN comun_transaction ct ON tr.id_transactionai = ct.id_transaction
    """
    if wheres:
        base_query += " WHERE " + " AND ".join(wheres)
    base_query += " ORDER BY tr.date DESC LIMIT 5000"

    with get_cursor("DB") as cur:
        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()
    df = pd.DataFrame(rows)

    if df.empty:
        return df

    org_ids = df["id_organizacion"].dropna().unique().tolist()

    if org_ids:
        id_to_name = _organization_id_to_name(org_ids)
        df["organization_name"] = df["id_organizacion"].map(id_to_name)
    else:
        df["organization_name"] = None

    return df

def distinct_product_accounts() -> List[str]:
    with get_cursor("DB") as cur:
        cur.execute("SELECT DISTINCT product_account FROM transaction ORDER BY 1")
        return [r["product_account"] for r in cur.fetchall() if r["product_account"]]

def distinct_organization_names() -> List[str]:
    with get_cursor("ORG_DB") as cur:
        cur.execute("SELECT DISTINCT nombre FROM organizaciones WHERE id_organizacion IN (1,11,12,13,14) ORDER BY 1")
        return [r["nombre"] for r in cur.fetchall() if r["nombre"]]

def update_conciliation(transaction_ids: List[int], status: str) -> None:
    if status not in {"CONCILIATED", "NOT_CONCILIATED"}:
        raise ValueError("status must be 'CONCILIATED' or 'NOT_CONCILIATED'")

    if not transaction_ids:
        return

    placeholders = ",".join(["%s"] * len(transaction_ids))

    with get_cursor("DB") as cur:
        cur.execute(
            f"UPDATE transaction SET conciliation = %s WHERE id_transactionai IN ({placeholders})",
            (status, *transaction_ids),
        )
        cur.execute(
            f"UPDATE comun_transaction SET conciliation = %s, conciliation_status = %s WHERE id_transaction IN ({placeholders})",
            (status, status, *transaction_ids),
        )

def _organization_id_to_name(ids: List[int]) -> Dict[int, str]:
    placeholders = ",".join(["%s"] * len(ids))
    query = f"SELECT id_organizacion, nombre FROM organizaciones WHERE id_organizacion IN ({placeholders})"
    with get_cursor("ORG_DB") as cur:
        cur.execute(query, tuple(ids))
        return {row["id_organizacion"]: row["nombre"] for row in cur.fetchall()}

def _organization_name_to_id() -> Dict[str, int]:
    with get_cursor("ORG_DB") as cur:
        cur.execute("SELECT id_organizacion, nombre FROM organizaciones")
        return {row["nombre"]: row["id_organizacion"] for row in cur.fetchall()}