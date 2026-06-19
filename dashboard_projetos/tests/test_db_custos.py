import pandas as pd
from utils.db import salvar_custos, carregar_custos, listar_importacoes, deletar_importacao

ARQUIVO_TESTE = "custos__teste_pytest__.csv"


def _df_custos_exemplo():
    return pd.DataFrame({
        "centro_de_custo": ["100150268"],
        "ano": ["2026"],
        "mes": ["Janeiro"],
        "realizado": [1000.50],
    })


def test_salvar_e_carregar_custos():
    linhas, duplicado = salvar_custos(_df_custos_exemplo(), ARQUIVO_TESTE)
    assert linhas == 1
    assert duplicado is False

    df = carregar_custos()
    assert (df["arquivo"] == ARQUIVO_TESTE).sum() == 1
    linha = df[df["arquivo"] == ARQUIVO_TESTE].iloc[0]
    assert linha["centro_de_custo"] == "100150268"
    assert float(linha["realizado"]) == 1000.50


def test_salvar_custos_duplicado_e_ignorado():
    salvar_custos(_df_custos_exemplo(), ARQUIVO_TESTE)
    linhas, duplicado = salvar_custos(_df_custos_exemplo(), ARQUIVO_TESTE)
    assert linhas == 0
    assert duplicado is True


def test_listar_importacoes_inclui_arquivo_salvo():
    salvar_custos(_df_custos_exemplo(), ARQUIVO_TESTE)
    df_imp = listar_importacoes()
    assert (df_imp["arquivo"] == ARQUIVO_TESTE).any()


def test_deletar_importacao_remove_linhas():
    salvar_custos(_df_custos_exemplo(), ARQUIVO_TESTE)
    removidas = deletar_importacao(ARQUIVO_TESTE, "custos")
    assert removidas == 1
    df = carregar_custos()
    assert (df["arquivo"] == ARQUIVO_TESTE).sum() == 0
