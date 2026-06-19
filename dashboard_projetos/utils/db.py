"""
db.py — camada de persistência Postgres (Supabase)
- Schema idempotente (CREATE TABLE IF NOT EXISTS + migração de colunas)
- Conexão via SQLAlchemy Engine, cacheada por processo (st.cache_resource)
- Suporte a nomes de projeto editáveis e previsões por período
"""
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _database_url() -> str:
    """
    Retorna a connection string Postgres a partir de st.secrets (produção)
    ou variável de ambiente DATABASE_URL (uso local).
    """
    try:
        if "DATABASE_URL" in st.secrets:
            return str(st.secrets["DATABASE_URL"])
    except Exception:
        pass
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL não configurado. Defina nos Secrets do Streamlit "
            "Cloud (produção) ou em .streamlit/secrets.toml / variável de "
            "ambiente (uso local)."
        )
    return url


@st.cache_resource(show_spinner=False)
def _engine() -> Engine:
    return create_engine(_database_url(), pool_pre_ping=True)


def _agora() -> str:
    """Timestamp atual no formato usado pelas colunas TEXT de data/hora."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
