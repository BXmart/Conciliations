"""Streamlit entry‑point for the conciliations dashboard."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from auth import login
from db import distinct_product_accounts, distinct_organization_names, fetch_transactions, update_conciliation

###############################################################################
# Page config & authentication
###############################################################################

st.set_page_config(
    page_title="⚖️ Transaction Conciliations",
    page_icon="💳",
    layout="wide",
)

st.title("💳 Transaction Conciliations")

if not login():
    st.stop()  # unauthenticated users cannot continue

###############################################################################
# Sidebar filters
###############################################################################

def sidebar_filters():
    """Render sidebar widgets, return dict with the selected filter values."""
    with st.sidebar:
        st.header("🔍 Filtros")

        # Date range ---------------------------------------------------------
        today = dt.date.today()
        default_from = today.replace(day=1)  # first day of this month
        date_from, date_to = st.date_input(
            "Rango de fechas",
            value=(default_from, today),
            max_value=today,
        )
        # Product accounts ---------------------------------------------------
        products = distinct_product_accounts()
        product_accounts = st.multiselect(
            "Product account",
            products,
            placeholder="Todas…",
        )
        # Description search --------------------------------------------------
        description_search = st.text_input(
            "Descripción contiene…",
            placeholder="Busca en texto de descripción",
        )
        # Organizations -------------------------------------------------------
        org_names = distinct_organization_names()
        organization_names = st.multiselect(
            "Organización",
            org_names,
            placeholder="Todas…",
        )

    return {
        "date_from": date_from,
        "date_to": date_to,
        "product_accounts": product_accounts or None,
        "description_search": description_search or None,
        "organization_names": organization_names or None,
    }

filters = sidebar_filters()

###############################################################################
# Fetch data & show table
###############################################################################

@st.cache_data(ttl=300, show_spinner="Cargando transacciones…")
def load_data(_filters: dict) -> pd.DataFrame:
    return fetch_transactions(**_filters)

df = load_data(filters)

if df.empty:
    st.info("No se encontraron transacciones con esos filtros.")
    st.stop()

# Add a checkbox column for selection ----------------------------------------

selection_col = "✅ Conciliar"
if selection_col not in df.columns:
    df.insert(0, selection_col, False)

edited_df = st.data_editor(
    df,
    use_container_width=True,
    num_rows="dynamic",
    key="transactions_editor",
    height=480,
)

selected_ids = edited_df[edited_df[selection_col]].id_transactionai.tolist()

###############################################################################
# Action buttons
###############################################################################

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