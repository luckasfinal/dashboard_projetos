import io
import pandas as pd

from utils.data_processor import importar_orcamento_de_excel
from utils.db import carregar_orcamento_projeto, carregar_previsoes_projeto

PROJETO_TESTE = "PROJIMP__teste_pytest__"


def _xlsx_orcamento_e_previsao():
    df_orc = pd.DataFrame([{
        "projeto": PROJETO_TESTE,
        "nome_projeto_editado": "Projeto Importado",
        "orcamento_previsto": 12000.0,
        "status_projeto": "Viabilizado",
        "data_inicio": "2026-01-01",
    }])
    df_prev = pd.DataFrame([{
        "projeto": PROJETO_TESTE,
        "periodo": "2026",
        "tipo_periodo": "anual",
        "valor": 9000.0,
        "descricao": "Previsao importada",
    }])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_orc.to_excel(writer, sheet_name="Orcamentos", index=False)
        df_prev.to_excel(writer, sheet_name="Previsoes", index=False)
    return buf.getvalue()


def test_importar_orcamento_de_excel_salva_orcamento_e_previsao():
    importados = importar_orcamento_de_excel(_xlsx_orcamento_e_previsao())

    assert importados == 1
    dados = carregar_orcamento_projeto(PROJETO_TESTE)
    assert dados is not None
    assert float(dados["orcamento_previsto"]) == 12000.0
    assert dados["status_projeto"] == "Viabilizado"

    df_prev = carregar_previsoes_projeto(PROJETO_TESTE)
    assert (df_prev["periodo"] == "2026").any()


def test_importar_orcamento_de_excel_ignora_linha_sem_projeto():
    df_orc = pd.DataFrame([{"projeto": "", "orcamento_previsto": 100.0}])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_orc.to_excel(writer, sheet_name="Orcamentos", index=False)

    importados = importar_orcamento_de_excel(buf.getvalue())
    assert importados == 0


def test_importar_orcamento_de_excel_trata_celulas_vazias_como_nulas():
    nome = "PROJIMP2__teste_pytest__"
    df_orc = pd.DataFrame([{
        "projeto": nome,
        "orcamento_previsto": None,
        "data_inicio": None,
    }])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_orc.to_excel(writer, sheet_name="Orcamentos", index=False)

    importados = importar_orcamento_de_excel(buf.getvalue())
    assert importados == 1

    dados = carregar_orcamento_projeto(nome)
    assert dados is not None
    assert float(dados["orcamento_previsto"]) == 0.0
    assert dados["data_inicio"] is None
