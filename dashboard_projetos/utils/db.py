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


# ─────────────────────────────────────────────────────
# Gravação e leitura — custos
# ─────────────────────────────────────────────────────

def _ja_importado(arquivo: str, tipo: str) -> bool:
    with _engine().connect() as con:
        row = con.execute(
            text("SELECT 1 FROM importacoes WHERE arquivo = :arquivo AND tipo = :tipo LIMIT 1"),
            {"arquivo": arquivo, "tipo": tipo},
        ).fetchone()
        return row is not None


def salvar_custos(df: pd.DataFrame, nome_arquivo: str) -> tuple[int, bool]:
    if _ja_importado(nome_arquivo, "custos"):
        return 0, True
    df_ins = df.reindex(columns=COLUNAS_DB_CUSTOS)
    df_ins["arquivo"] = nome_arquivo
    df_ins["importado_em"] = _agora()
    with _engine().begin() as con:
        df_ins.to_sql("custos", con, if_exists="append", index=False)
        con.execute(
            text(
                "INSERT INTO importacoes (arquivo, tipo, linhas, importado_em) "
                "VALUES (:arquivo, 'custos', :linhas, :agora)"
            ),
            {"arquivo": nome_arquivo, "linhas": len(df_ins), "agora": _agora()},
        )
    return len(df_ins), False


def carregar_custos() -> pd.DataFrame:
    with _engine().connect() as con:
        return pd.read_sql(text("SELECT * FROM custos"), con)


def listar_importacoes() -> pd.DataFrame:
    with _engine().connect() as con:
        return pd.read_sql(
            text(
                "SELECT tipo, arquivo, importado_em, linhas FROM importacoes "
                "ORDER BY importado_em DESC"
            ),
            con,
        )


def deletar_importacao(nome_arquivo: str, tipo: str) -> int:
    tabela = "custos" if tipo == "custos" else "horas"
    with _engine().begin() as con:
        resultado = con.execute(
            text(f"DELETE FROM {tabela} WHERE arquivo = :arquivo"),
            {"arquivo": nome_arquivo},
        )
        con.execute(
            text("DELETE FROM importacoes WHERE arquivo = :arquivo AND tipo = :tipo"),
            {"arquivo": nome_arquivo, "tipo": tipo},
        )
        return resultado.rowcount


# ─────────────────────────────────────────────────────
# Gravação e leitura — horas
# ─────────────────────────────────────────────────────

def salvar_horas(df: pd.DataFrame, nome_arquivo: str) -> tuple[int, bool]:
    if _ja_importado(nome_arquivo, "horas"):
        return 0, True
    df_ins = df.reindex(columns=COLUNAS_DB_HORAS)
    df_ins["arquivo"] = nome_arquivo
    df_ins["importado_em"] = _agora()
    with _engine().begin() as con:
        df_ins.to_sql("horas", con, if_exists="append", index=False)
        con.execute(
            text(
                "INSERT INTO importacoes (arquivo, tipo, linhas, importado_em) "
                "VALUES (:arquivo, 'horas', :linhas, :agora)"
            ),
            {"arquivo": nome_arquivo, "linhas": len(df_ins), "agora": _agora()},
        )
    return len(df_ins), False


def carregar_horas() -> pd.DataFrame:
    with _engine().connect() as con:
        return pd.read_sql(text("SELECT * FROM horas"), con)


# ─────────────────────────────────────────────────────
# Gravação e leitura — orçamentos / cronograma
# ─────────────────────────────────────────────────────

def salvar_orcamento(
    projeto: str,
    orcamento_previsto: float,
    data_inicio: str | None,
    prev_viabilidade: str | None,
    prev_qualidade: str | None,
    prev_aprov_lancamento: str | None,
    prev_lancamento: str | None,
    real_viabilidade: str | None,
    real_qualidade: str | None,
    real_aprov_lancamento: str | None,
    real_lancamento: str | None,
    nome_projeto_editado: str | None = None,
    status_projeto: str | None = None,
) -> None:
    with _engine().begin() as con:
        con.execute(text("""
            INSERT INTO orcamentos_cronograma (
                projeto, nome_projeto_editado, orcamento_previsto, status_projeto, data_inicio,
                prev_viabilidade, prev_qualidade, prev_aprov_lancamento, prev_lancamento,
                real_viabilidade, real_qualidade, real_aprov_lancamento, real_lancamento,
                atualizado_em
            ) VALUES (
                :projeto, :nome_projeto_editado, :orcamento_previsto, :status_projeto, :data_inicio,
                :prev_viabilidade, :prev_qualidade, :prev_aprov_lancamento, :prev_lancamento,
                :real_viabilidade, :real_qualidade, :real_aprov_lancamento, :real_lancamento,
                :atualizado_em
            )
            ON CONFLICT (projeto) DO UPDATE SET
                nome_projeto_editado    = excluded.nome_projeto_editado,
                orcamento_previsto      = excluded.orcamento_previsto,
                status_projeto          = excluded.status_projeto,
                data_inicio             = excluded.data_inicio,
                prev_viabilidade        = excluded.prev_viabilidade,
                prev_qualidade          = excluded.prev_qualidade,
                prev_aprov_lancamento   = excluded.prev_aprov_lancamento,
                prev_lancamento         = excluded.prev_lancamento,
                real_viabilidade        = excluded.real_viabilidade,
                real_qualidade          = excluded.real_qualidade,
                real_aprov_lancamento   = excluded.real_aprov_lancamento,
                real_lancamento         = excluded.real_lancamento,
                atualizado_em           = excluded.atualizado_em
        """), {
            "projeto": projeto,
            "nome_projeto_editado": nome_projeto_editado,
            "orcamento_previsto": orcamento_previsto,
            "status_projeto": status_projeto,
            "data_inicio": data_inicio,
            "prev_viabilidade": prev_viabilidade,
            "prev_qualidade": prev_qualidade,
            "prev_aprov_lancamento": prev_aprov_lancamento,
            "prev_lancamento": prev_lancamento,
            "real_viabilidade": real_viabilidade,
            "real_qualidade": real_qualidade,
            "real_aprov_lancamento": real_aprov_lancamento,
            "real_lancamento": real_lancamento,
            "atualizado_em": _agora(),
        })


def carregar_orcamentos() -> pd.DataFrame:
    with _engine().connect() as con:
        return pd.read_sql(text("SELECT * FROM orcamentos_cronograma"), con)


def carregar_orcamento_projeto(projeto: str) -> dict | None:
    with _engine().connect() as con:
        resultado = con.execute(
            text("SELECT * FROM orcamentos_cronograma WHERE projeto = :projeto"),
            {"projeto": projeto},
        )
        linha = resultado.fetchone()
        if linha is None:
            return None
        return dict(linha._mapping)


def deletar_orcamento_projeto(projeto: str) -> bool:
    with _engine().begin() as con:
        resultado = con.execute(
            text("DELETE FROM orcamentos_cronograma WHERE projeto = :projeto"),
            {"projeto": projeto},
        )
        return resultado.rowcount > 0
