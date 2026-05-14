"""
data_processor.py — lógica de transformação e agregação
Lê sempre do banco SQLite (histórico completo acumulado).
"""
import io
import pandas as pd
import streamlit as st
from pathlib import Path

from utils.db import carregar_custos, carregar_horas

# ─────────────────────────────────────────────
# Schemas esperados
# ─────────────────────────────────────────────
COLUNAS_CUSTOS = {
    "projeto":   str,
    "categoria": str,
    "valor":     float,
    "data":      str,
    "orcamento": float,
    "status":    str,
}

COLUNAS_HORAS = {
    "projeto":     str,
    "colaborador": str,
    "horas":       float,
    "data":        str,
    "tarefa":      str,
}


# ─────────────────────────────────────────────
# Leitura de arquivo enviado pelo usuário
# ─────────────────────────────────────────────

def ler_planilha_bytes(conteudo: bytes, nome: str) -> pd.DataFrame:
    if nome.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(conteudo))
    return pd.read_excel(io.BytesIO(conteudo))


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def validar_colunas(df: pd.DataFrame, esperadas: dict, nome: str) -> list[str]:
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        return [f"**{nome}** — colunas ausentes: `{', '.join(faltando)}`"]
    return []


def preparar_custos(df: pd.DataFrame) -> pd.DataFrame:
    df = normalizar_colunas(df)
    df["valor"]     = pd.to_numeric(df.get("valor",    0), errors="coerce").fillna(0)
    df["orcamento"] = pd.to_numeric(df.get("orcamento", 0), errors="coerce").fillna(0)
    if "projeto" in df.columns:
        df["projeto"] = df["projeto"].astype(str).str.strip().str.title()
    return df


def preparar_horas(df: pd.DataFrame) -> pd.DataFrame:
    df = normalizar_colunas(df)
    df["horas"] = pd.to_numeric(df.get("horas", 0), errors="coerce").fillna(0)
    if "projeto" in df.columns:
        df["projeto"] = df["projeto"].astype(str).str.strip().str.title()
    return df


# ─────────────────────────────────────────────
# Agregação completa (lê do banco)
# ─────────────────────────────────────────────

@st.cache_data(ttl=5, show_spinner="Carregando dados históricos…")
def agregar_tudo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Lê TODO o histórico do banco e retorna:
      (df_merged, df_custos_raw, df_horas_raw)
    Cache TTL de 5 s — invalida automaticamente após novo upload.
    """
    df_custos = carregar_custos()
    df_horas  = carregar_horas()

    if df_custos.empty and df_horas.empty:
        return pd.DataFrame(), df_custos, df_horas

    # Prepara tipos
    if not df_custos.empty:
        df_custos["valor"]     = pd.to_numeric(df_custos["valor"],     errors="coerce").fillna(0)
        df_custos["orcamento"] = pd.to_numeric(df_custos["orcamento"], errors="coerce").fillna(0)
        df_custos["projeto"]   = df_custos["projeto"].astype(str).str.strip().str.title()
        if "data" in df_custos.columns:
            df_custos["mes"] = pd.to_datetime(df_custos["data"], errors="coerce").dt.to_period("M").astype(str)

    if not df_horas.empty:
        df_horas["horas"]   = pd.to_numeric(df_horas["horas"], errors="coerce").fillna(0)
        df_horas["projeto"] = df_horas["projeto"].astype(str).str.strip().str.title()
        if "data" in df_horas.columns:
            df_horas["mes"] = pd.to_datetime(df_horas["data"], errors="coerce").dt.to_period("M").astype(str)

    # Agrega por projeto
    if not df_custos.empty:
        custos_agg = df_custos.groupby("projeto").agg(
            valor_total=("valor", "sum"),
            orcamento=("orcamento", "max"),
            categorias=("categoria", lambda x: ", ".join(x.dropna().unique())),
            status=("status", "last"),
        ).reset_index()
    else:
        custos_agg = pd.DataFrame(columns=["projeto","valor_total","orcamento","categorias","status"])

    if not df_horas.empty:
        horas_agg = df_horas.groupby("projeto").agg(
            horas_total=("horas", "sum"),
            n_colaboradores=("colaborador", "nunique"),
            colaboradores=("colaborador", lambda x: ", ".join(x.dropna().unique())),
        ).reset_index()
    else:
        horas_agg = pd.DataFrame(columns=["projeto","horas_total","n_colaboradores","colaboradores"])

    merged = custos_agg.merge(horas_agg, on="projeto", how="outer").fillna(0)

    # KPIs derivados
    merged["custo_por_hora"]  = merged.apply(
        lambda r: r["valor_total"] / r["horas_total"] if r["horas_total"] > 0 else 0, axis=1
    )
    merged["pct_orcamento"]   = merged.apply(
        lambda r: min(r["valor_total"] / r["orcamento"] * 100, 100) if r["orcamento"] > 0 else 0, axis=1
    )
    merged["saldo_orcamento"] = merged["orcamento"] - merged["valor_total"]

    return merged, df_custos, df_horas


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def formata_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cor_status(pct: float) -> str:
    if pct >= 90:
        return "🔴"
    if pct >= 70:
        return "🟡"
    return "🟢"
