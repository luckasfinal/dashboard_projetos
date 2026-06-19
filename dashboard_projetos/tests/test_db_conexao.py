from sqlalchemy import text
from utils.db import _engine


def test_consegue_conectar_no_postgres():
    with _engine().connect() as con:
        resultado = con.execute(text("SELECT 1")).scalar()
    assert resultado == 1
