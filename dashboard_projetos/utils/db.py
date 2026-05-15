"""
db.py — camada de persistência SQLite
Suporta migração automática: se o banco já existe com schema antigo,
adiciona as colunas novas sem apagar dados.
"""
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "dashboard.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


# ─────────────────────────────────────────────────────
# Definição completa das colunas esperadas
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

# Tipo SQLite de cada coluna (usado na migração)
TIPOS_CUSTOS = {
    "data": "TEXT", "ano": "TEXT", "mes": "TEXT", "filial": "TEXT",
    "area": "TEXT", "centro_de_custo": "TEXT", "conta": "TEXT",
    "cod_parceiro_negocio": "TEXT", "parceiro_negocio": "TEXT",
    "historico": "TEXT", "realizado": "REAL",
}

TIPOS_HORAS = {
    "periodo": "TEXT", "c_custo": "TEXT", "ordem_interna": "TEXT",
    "descricao_ordem_interna": "TEXT", "centro_de_lucro": "TEXT",
    "descricao_c_lucro": "TEXT", "matricula": "TEXT", "nome": "TEXT",
    "cc_origem": "TEXT", "descricao_cc_origem": "TEXT", "hs_nor": "REAL",
    "tipo_de_projeto": "TEXT", "cod_produto": "TEXT", "descricao_produto": "TEXT",
    "categoria": "TEXT", "atividade": "TEXT", "detalhes": "TEXT",
    "c_custo_descricao_ordem_interna": "TEXT", "matricula_nome": "TEXT",
    "segmento": "TEXT",
}


def init_db() -> None:
    """Cria as tabelas se ainda não existirem."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS custos (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                arquivo      TEXT NOT NULL,
                importado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                data         TEXT, ano TEXT, mes TEXT, filial TEXT, area TEXT,
                centro_de_custo TEXT, conta TEXT, cod_parceiro_negocio TEXT,
                parceiro_negocio TEXT, historico TEXT, realizado REAL
            );

            CREATE TABLE IF NOT EXISTS horas (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                arquivo      TEXT NOT NULL,
                importado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                periodo TEXT, c_custo TEXT, ordem_interna TEXT,
                descricao_ordem_interna TEXT, centro_de_lucro TEXT,
                descricao_c_lucro TEXT, matricula TEXT, nome TEXT,
                cc_origem TEXT, descricao_cc_origem TEXT, hs_nor REAL,
                tipo_de_projeto TEXT, cod_produto TEXT, descricao_produto TEXT,
                categoria TEXT, atividade TEXT, detalhes TEXT,
                c_custo_descricao_ordem_interna TEXT, matricula_nome TEXT,
                segmento TEXT
            );

            CREATE TABLE IF NOT EXISTS importacoes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                arquivo      TEXT NOT NULL,
                tipo         TEXT NOT NULL,
                importado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                linhas       INTEGER
            );
        """)


def migrar_db() -> None:
    """
    Adiciona colunas que ainda não existem no banco (migração não-destrutiva).
    Garante que um banco criado com schema antigo funcione sem perder dados.
    """
    with _conn() as con:
        for tabela, colunas, tipos in [
            ("custos", COLUNAS_DB_CUSTOS, TIPOS_CUSTOS),
            ("horas",  COLUNAS_DB_HORAS,  TIPOS_HORAS),
        ]:
            # Lê colunas existentes
            cur = con.execute(f"PRAGMA table_info({tabela})")
            existentes = {row[1] for row in cur.fetchall()}

            for col in colunas:
                if col not in existentes:
                    tipo = tipos.get(col, "TEXT")
                    con.execute(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}")


# ─────────────────────────────────────────────────────
# Gravação
# ─────────────────────────────────────────────────────

def _ja_importado(arquivo: str, tipo: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "SELECT 1 FROM importacoes WHERE arquivo = ? AND tipo = ? LIMIT 1",
            (arquivo, tipo),
        )
        return cur.fetchone() is not None


def salvar_custos(df: pd.DataFrame, nome_arquivo: str) -> tuple[int, bool]:
    if _ja_importado(nome_arquivo, "custos"):
        return 0, True
    df_ins = df.reindex(columns=COLUNAS_DB_CUSTOS)
    df_ins["arquivo"] = nome_arquivo
    with _conn() as con:
        df_ins.to_sql("custos", con, if_exists="append", index=False)
        con.execute(
            "INSERT INTO importacoes (arquivo, tipo, linhas) VALUES (?, 'custos', ?)",
            (nome_arquivo, len(df_ins)),
        )
    return len(df_ins), False


def salvar_horas(df: pd.DataFrame, nome_arquivo: str) -> tuple[int, bool]:
    if _ja_importado(nome_arquivo, "horas"):
        return 0, True
    df_ins = df.reindex(columns=COLUNAS_DB_HORAS)
    df_ins["arquivo"] = nome_arquivo
    with _conn() as con:
        df_ins.to_sql("horas", con, if_exists="append", index=False)
        con.execute(
            "INSERT INTO importacoes (arquivo, tipo, linhas) VALUES (?, 'horas', ?)",
            (nome_arquivo, len(df_ins)),
        )
    return len(df_ins), False


# ─────────────────────────────────────────────────────
# Leitura
# ─────────────────────────────────────────────────────

def carregar_custos() -> pd.DataFrame:
    with _conn() as con:
        return pd.read_sql("SELECT * FROM custos", con)


def carregar_horas() -> pd.DataFrame:
    with _conn() as con:
        return pd.read_sql("SELECT * FROM horas", con)


def listar_importacoes() -> pd.DataFrame:
    with _conn() as con:
        return pd.read_sql(
            "SELECT tipo, arquivo, importado_em, linhas FROM importacoes ORDER BY importado_em DESC",
            con,
        )


# ─────────────────────────────────────────────────────
# Deleção
# ─────────────────────────────────────────────────────

def deletar_importacao(nome_arquivo: str, tipo: str) -> int:
    with _conn() as con:
        tabela = "custos" if tipo == "custos" else "horas"
        cur = con.execute(f"DELETE FROM {tabela} WHERE arquivo = ?", (nome_arquivo,))
        con.execute(
            "DELETE FROM importacoes WHERE arquivo = ? AND tipo = ?",
            (nome_arquivo, tipo),
        )
        return cur.rowcount


def limpar_tudo() -> None:
    with _conn() as con:
        con.executescript("DELETE FROM custos; DELETE FROM horas; DELETE FROM importacoes;")
