from sqlalchemy import text
from utils.db import _engine, init_db, migrar_db


def test_tabelas_sao_criadas():
    init_db()
    with _engine().connect() as con:
        tabelas = {
            row[0] for row in con.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            ).fetchall()
        }
    esperadas = {
        "custos", "horas", "importacoes",
        "orcamentos_cronograma", "previsoes_periodo",
    }
    assert esperadas.issubset(tabelas)


def test_migrar_db_e_idempotente():
    init_db()
    migrar_db()
    migrar_db()  # rodar duas vezes não deve lançar erro
