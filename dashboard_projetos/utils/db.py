"""
db.py — camada de persistência SQLite
Todos os dados enviados ficam salvos no arquivo data/dashboard.db
Novos uploads somam ao histórico sem apagar o que já existe.
"""
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "dashboard.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db() -> None:
    """Cria as tabelas se ainda não existirem."""
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS custos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                arquivo     TEXT    NOT NULL,
                importado_em TEXT   NOT NULL DEFAULT (datetime('now','localtime')),
                projeto     TEXT,
                categoria   TEXT,
                valor       REAL,
                data        TEXT,
                orcamento   REAL,
                status      TEXT
            );

            CREATE TABLE IF NOT EXISTS horas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                arquivo     TEXT    NOT NULL,
                importado_em TEXT   NOT NULL DEFAULT (datetime('now','localtime')),
                projeto     TEXT,
                colaborador TEXT,
                horas       REAL,
                data        TEXT,
                tarefa      TEXT
            );

            CREATE TABLE IF NOT EXISTS importacoes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                arquivo      TEXT    NOT NULL,
                tipo         TEXT    NOT NULL,   -- 'custos' ou 'horas'
                importado_em TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                linhas       INTEGER
            );
        """)


# ──────────────────────────────────────────────
# Gravação
# ──────────────────────────────────────────────

def _ja_importado(arquivo: str, tipo: str) -> bool:
    """Retorna True se esse arquivo já foi importado antes."""
    with _conn() as con:
        cur = con.execute(
            "SELECT 1 FROM importacoes WHERE arquivo = ? AND tipo = ? LIMIT 1",
            (arquivo, tipo),
        )
        return cur.fetchone() is not None


def salvar_custos(df: pd.DataFrame, nome_arquivo: str) -> tuple[int, bool]:
    """
    Insere as linhas de custos no banco.
    Retorna (linhas_inseridas, ja_existia).
    Se o arquivo já foi importado antes, não duplica — retorna (0, True).
    """
    if _ja_importado(nome_arquivo, "custos"):
        return 0, True

    colunas = ["projeto", "categoria", "valor", "data", "orcamento", "status"]
    df_ins = df.reindex(columns=colunas)
    df_ins["arquivo"] = nome_arquivo

    with _conn() as con:
        df_ins.to_sql("custos", con, if_exists="append", index=False)
        con.execute(
            "INSERT INTO importacoes (arquivo, tipo, linhas) VALUES (?, 'custos', ?)",
            (nome_arquivo, len(df_ins)),
        )
    return len(df_ins), False


def salvar_horas(df: pd.DataFrame, nome_arquivo: str) -> tuple[int, bool]:
    """Insere as linhas de horas. Mesmo comportamento de deduplicação."""
    if _ja_importado(nome_arquivo, "horas"):
        return 0, True

    colunas = ["projeto", "colaborador", "horas", "data", "tarefa"]
    df_ins = df.reindex(columns=colunas)
    df_ins["arquivo"] = nome_arquivo

    with _conn() as con:
        df_ins.to_sql("horas", con, if_exists="append", index=False)
        con.execute(
            "INSERT INTO importacoes (arquivo, tipo, linhas) VALUES (?, 'horas', ?)",
            (nome_arquivo, len(df_ins)),
        )
    return len(df_ins), False


# ──────────────────────────────────────────────
# Leitura
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# Deleção seletiva
# ──────────────────────────────────────────────

def deletar_importacao(nome_arquivo: str, tipo: str) -> int:
    """Remove todos os registros de um arquivo específico. Retorna linhas removidas."""
    with _conn() as con:
        tabela = "custos" if tipo == "custos" else "horas"
        cur = con.execute(f"DELETE FROM {tabela} WHERE arquivo = ?", (nome_arquivo,))
        con.execute(
            "DELETE FROM importacoes WHERE arquivo = ? AND tipo = ?",
            (nome_arquivo, tipo),
        )
        return cur.rowcount


def limpar_tudo() -> None:
    """Apaga todos os dados do banco (botão reset)."""
    with _conn() as con:
        con.executescript("DELETE FROM custos; DELETE FROM horas; DELETE FROM importacoes;")
