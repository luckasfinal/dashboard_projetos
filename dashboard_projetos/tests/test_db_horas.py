import pandas as pd
from utils.db import salvar_horas, carregar_horas

ARQUIVO_TESTE = "horas__teste_pytest__.csv"


def _df_horas_exemplo():
    return pd.DataFrame({
        "c_custo": ["100150268"],
        "nome": ["Colaborador Teste"],
        "periodo": ["01/01/2026"],
        "hs_nor": [8.0],
    })


def test_salvar_e_carregar_horas():
    linhas, duplicado = salvar_horas(_df_horas_exemplo(), ARQUIVO_TESTE)
    assert linhas == 1
    assert duplicado is False

    df = carregar_horas()
    linha = df[df["arquivo"] == ARQUIVO_TESTE].iloc[0]
    assert linha["c_custo"] == "100150268"
    assert float(linha["hs_nor"]) == 8.0


def test_salvar_horas_duplicado_e_ignorado():
    salvar_horas(_df_horas_exemplo(), ARQUIVO_TESTE)
    linhas, duplicado = salvar_horas(_df_horas_exemplo(), ARQUIVO_TESTE)
    assert linhas == 0
    assert duplicado is True
