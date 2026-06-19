import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in [str(ROOT), str(ROOT / "utils")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import text  # noqa: E402
from utils.db import init_db, migrar_db, _engine  # noqa: E402

MARCADOR_TESTE = "__teste_pytest__"


@pytest.fixture(scope="session", autouse=True)
def _preparar_schema():
    init_db()
    migrar_db()


@pytest.fixture(autouse=True)
def _limpar_dados_de_teste():
    yield
    with _engine().begin() as con:
        con.execute(text("DELETE FROM custos WHERE arquivo LIKE :m"), {"m": f"%{MARCADOR_TESTE}%"})
        con.execute(text("DELETE FROM horas WHERE arquivo LIKE :m"), {"m": f"%{MARCADOR_TESTE}%"})
        con.execute(text("DELETE FROM importacoes WHERE arquivo LIKE :m"), {"m": f"%{MARCADOR_TESTE}%"})
        con.execute(text("DELETE FROM orcamentos_cronograma WHERE projeto LIKE :m"), {"m": f"%{MARCADOR_TESTE}%"})
        con.execute(text("DELETE FROM previsoes_periodo WHERE projeto LIKE :m"), {"m": f"%{MARCADOR_TESTE}%"})
