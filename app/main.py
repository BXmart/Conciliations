from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from auth import login
from db import fetch_transactions, distinct_product_accounts, distinct_organization_names, update_conciliation

st.set_page_config(
    page_title="⚖️ Conciliaciones",
    page_icon="💳",
    layout="wide",
)

st.title("💳 Conciliaciones")

if not login():
    st.stop()

def sidebar_filters():
    with st.sidebar:
        st.header("🔍 Filtros")

        today = dt.date.today()
        default_from = today.replace(day=1)
        date_from, date_to = st.date_input(
            "Rango de fechas",
            value=(default_from, today),
            max_value=today,
        )

        id_transaction = st.text_input("Id Transacción", value="")
        id_transaction = int(id_transaction) if id_transaction.strip().isdigit() else None

        products = distinct_product_accounts()
        product_accounts = st.multiselect(
            "Producto bancario",
            options=products,
            default=[],
            placeholder="Todas…",
        )

        description_search = st.text_input(
            "Descripción contiene…",
            value="",
            placeholder="Busca en texto de descripción",
        )

        org_names = distinct_organization_names()
        organization_names = st.multiselect(
            "Organización",
            options=org_names,
            default=[],
            placeholder="Todas…",
        )

    return {
        "date_from": date_from,
        "date_to": date_to,
        "product_accounts": product_accounts or None,
        "description_search": description_search.strip() or None,
        "organization_names": organization_names or None,
        "id_transaction": id_transaction,
    }

filters = sidebar_filters()

@st.cache_data(ttl=300, show_spinner="Cargando transacciones…")
def load_data(
    date_from,
    date_to,
    product_accounts,
    description_search,
    organization_names,
    id_transaction,
):
    return fetch_transactions(
        date_from=date_from,
        date_to=date_to,
        product_accounts=product_accounts,
        description_search=description_search,
        organization_names=organization_names,
        id_transaction=id_transaction,
    )
df = load_data(**filters)

if df.empty:
    st.info("No se encontraron transacciones con esos filtros.")
    st.stop()

selection_col = "🔵 Conciliar"
if selection_col not in df.columns:
    df.insert(0, selection_col, False)

# Formatos
df["id_transactionai"] = df["id_transactionai"].astype(str)
    
# Renombrar columnas y reordenar
column_mapping = {
    "id_transactionai": "id",
    "date": "Fecha",
    "product_account": "Producto Bancario",
    "amount": "Cantidad (€)",
    "balance": "Balance (€)",
    "description": "Descripción",
    "conciliation": "Estado",
    "organization_name": "Organización",
    selection_col: "🔵 Conciliar"
}

df = df.rename(columns=column_mapping)
columns_order = ["🔵 Conciliar", "Estado", "id", "Fecha", "Organización", "Producto Bancario", "Descripción", "Cantidad (€)", "Balance (€)"]
df = df[columns_order]

edited_df = st.data_editor(
    df,
    use_container_width=True,
    num_rows="dynamic",
    key="transactions_editor",
    height=480,
    disabled=[col for col in df.columns if col != "🔵 Conciliar"]
)

selected_ids = edited_df[edited_df["🔵 Conciliar"]]["id"].tolist()

st.caption("Selecciona transacciones usando la columna de la izquierda y pulsa el botón correspondiente.")

col_a, col_b = st.columns(2)

with col_a:
    if st.button("Conciliar ✅", disabled=not selected_ids, type="primary"):
        update_conciliation(selected_ids, "CONCILIATED")
        st.success(f"{len(selected_ids)} transacciones conciliadas correctamente.")
        st.experimental_rerun()

with col_b:
    if st.button("Desconciliar ❌", disabled=not selected_ids, type="secondary"):
        update_conciliation(selected_ids, "NOT_CONCILIATED")
        st.warning(f"{len(selected_ids)} transacciones marcadas como NO conciliadas.")
        st.experimental_rerun()