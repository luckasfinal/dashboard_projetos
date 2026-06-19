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


# ─────────────────────────────────────────────────────
# Colunas esperadas por tabela
# ─────────────────────────────────────────────────────

COLUNAS_DB_CUSTOS = [
    "data", "ano", "mes", "filial", "area",
    "centro_de_custo", "conta", "cod_parceiro_negocio",
    "parceiro_negocio", "historico", "realizado",
]

COLUNAS_DB_HORAS = [
    "periodo", "c_custo", "ordem_interna", "descricao_ordem_interna",
    "centro_de_lucro", "descricao_c_lucro", "matricula", "nome",
    "cc_origem", "descricao_cc_origem", "hs_nor", "tipo_de_projeto",
    "cod_produto", "descricao_produto", "categoria", "atividade",
    "detalhes", "c_custo_descricao_ordem_interna", "matricula_nome", "segmento",
]

COLUNAS_DB_ORCAMENTOS = [
    "projeto", "nome_projeto_editado", "orcamento_previsto",
    "status_projeto",
    "data_inicio",
    "prev_viabilidade", "prev_qualidade", "prev_aprov_lancamento", "prev_lancamento",
    "real_viabilidade", "real_qualidade", "real_aprov_lancamento", "real_lancamento",
]

# ── Status do Projeto — opções fixas do dropdown ──────────────────────────────
STATUS_OPCOES = [
    "CC criado",
    "Viabilizado",
    "Aprovado em Critérios de Qualidade",
    "Aprovado para Lançamento",
    "Lançado",
    "Stand by",
    "Cancelado",
]
STATUS_DEFAULT = STATUS_OPCOES[0]

TIPOS_CUSTOS = {
    "data": "TEXT", "ano": "TEXT", "mes": "TEXT", "filial": "TEXT",
    "area": "TEXT", "centro_de_custo": "TEXT", "conta": "TEXT",
    "cod_parceiro_negocio": "TEXT", "parceiro_negocio": "TEXT",
    "historico": "TEXT", "realizado": "DOUBLE PRECISION",
}

TIPOS_HORAS = {
    "periodo": "TEXT", "c_custo": "TEXT", "ordem_interna": "TEXT",
    "descricao_ordem_interna": "TEXT", "centro_de_lucro": "TEXT",
    "descricao_c_lucro": "TEXT", "matricula": "TEXT", "nome": "TEXT",
    "cc_origem": "TEXT", "descricao_cc_origem": "TEXT", "hs_nor": "DOUBLE PRECISION",
    "tipo_de_projeto": "TEXT", "cod_produto": "TEXT", "descricao_produto": "TEXT",
    "categoria": "TEXT", "atividade": "TEXT", "detalhes": "TEXT",
    "c_custo_descricao_ordem_interna": "TEXT", "matricula_nome": "TEXT",
    "segmento": "TEXT",
}

TIPOS_ORCAMENTOS = {
    "projeto": "TEXT", "nome_projeto_editado": "TEXT",
    "orcamento_previsto": "DOUBLE PRECISION", "status_projeto": "TEXT",
    "data_inicio": "TEXT",
    "prev_viabilidade": "TEXT", "prev_qualidade": "TEXT",
    "prev_aprov_lancamento": "TEXT", "prev_lancamento": "TEXT",
    "real_viabilidade": "TEXT", "real_qualidade": "TEXT",
    "real_aprov_lancamento": "TEXT", "real_lancamento": "TEXT",
}


def init_db() -> None:
    """Cria tabelas se não existirem."""
    with _engine().begin() as con:
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS custos (
                id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                arquivo      TEXT NOT NULL,
                importado_em TEXT NOT NULL,
                data TEXT, ano TEXT, mes TEXT, filial TEXT, area TEXT,
                centro_de_custo TEXT, conta TEXT, cod_parceiro_negocio TEXT,
                parceiro_negocio TEXT, historico TEXT, realizado DOUBLE PRECISION
            )
        """))
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS horas (
                id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                arquivo      TEXT NOT NULL,
                importado_em TEXT NOT NULL,
                periodo TEXT, c_custo TEXT, ordem_interna TEXT,
                descricao_ordem_interna TEXT, centro_de_lucro TEXT,
                descricao_c_lucro TEXT, matricula TEXT, nome TEXT,
                cc_origem TEXT, descricao_cc_origem TEXT, hs_nor DOUBLE PRECISION,
                tipo_de_projeto TEXT, cod_produto TEXT, descricao_produto TEXT,
                categoria TEXT, atividade TEXT, detalhes TEXT,
                c_custo_descricao_ordem_interna TEXT, matricula_nome TEXT,
                segmento TEXT
            )
        """))
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS importacoes (
                id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                arquivo      TEXT NOT NULL,
                tipo         TEXT NOT NULL,
                importado_em TEXT NOT NULL,
                linhas       INTEGER
            )
        """))
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS orcamentos_cronograma (
                projeto                 TEXT PRIMARY KEY,
                nome_projeto_editado    TEXT,
                orcamento_previsto      DOUBLE PRECISION DEFAULT 0,
                status_projeto          TEXT DEFAULT 'CC criado',
                data_inicio             TEXT,
                prev_viabilidade        TEXT,
                prev_qualidade          TEXT,
                prev_aprov_lancamento   TEXT,
                prev_lancamento         TEXT,
                real_viabilidade        TEXT,
                real_qualidade          TEXT,
                real_aprov_lancamento   TEXT,
                real_lancamento         TEXT,
                atualizado_em           TEXT
            )
        """))
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS previsoes_periodo (
                id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projeto       TEXT NOT NULL,
                periodo       TEXT NOT NULL,
                tipo_periodo  TEXT NOT NULL DEFAULT 'anual',
                descricao     TEXT,
                valor         DOUBLE PRECISION NOT NULL DEFAULT 0,
                atualizado_em TEXT,
                UNIQUE(projeto, periodo, tipo_periodo)
            )
        """))


def migrar_db() -> None:
    """Migração não-destrutiva: adiciona colunas novas sem apagar dados."""
    with _engine().begin() as con:
        for tabela, colunas, tipos in [
            ("custos",                COLUNAS_DB_CUSTOS,     TIPOS_CUSTOS),
            ("horas",                 COLUNAS_DB_HORAS,      TIPOS_HORAS),
            ("orcamentos_cronograma", COLUNAS_DB_ORCAMENTOS, TIPOS_ORCAMENTOS),
        ]:
            existentes = {
                row[0] for row in con.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = :tabela"
                    ),
                    {"tabela": tabela},
                ).fetchall()
            }
            for col in colunas:
                if col not in existentes:
                    tipo = tipos.get(col, "TEXT")
                    con.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}"))
