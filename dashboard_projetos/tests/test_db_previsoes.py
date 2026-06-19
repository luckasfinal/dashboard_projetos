from utils.db import (
    salvar_previsao_periodo, carregar_previsoes_projeto,
    carregar_todas_previsoes, deletar_previsao_periodo,
)

PROJETO_TESTE = "PROJ__teste_pytest__"


def test_salvar_e_carregar_previsao():
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 10000.0, "anual", "Previsão inicial")
    df = carregar_previsoes_projeto(PROJETO_TESTE)
    assert len(df) == 1
    assert df.iloc[0]["periodo"] == "2026"
    assert float(df.iloc[0]["valor"]) == 10000.0


def test_salvar_previsao_e_upsert_por_periodo_e_tipo():
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 10000.0, "anual")
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 12000.0, "anual")
    df = carregar_previsoes_projeto(PROJETO_TESTE)
    assert len(df) == 1
    assert float(df.iloc[0]["valor"]) == 12000.0


def test_carregar_todas_previsoes_inclui_projeto_teste():
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 10000.0, "anual")
    df = carregar_todas_previsoes()
    assert (df["projeto"] == PROJETO_TESTE).any()


def test_deletar_previsao_periodo():
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 10000.0, "anual")
    df = carregar_previsoes_projeto(PROJETO_TESTE)
    id_prev = int(df.iloc[0]["id"])
    deletar_previsao_periodo(id_prev)
    df_depois = carregar_previsoes_projeto(PROJETO_TESTE)
    assert df_depois.empty
