import pandas as pd
from utils.db import (
    salvar_custos, salvar_horas, salvar_orcamento, salvar_previsao_periodo,
    deletar_projeto_completo, limpar_tudo, carregar_custos, carregar_horas,
    carregar_orcamento_projeto, carregar_previsoes_projeto,
)

PROJETO_TESTE = "100199__teste_pytest__"
ARQUIVO_CUSTOS = "custos_delecao__teste_pytest__.csv"
ARQUIVO_HORAS = "horas_delecao__teste_pytest__.csv"


def _popular_projeto_teste():
    salvar_custos(pd.DataFrame({
        "centro_de_custo": [PROJETO_TESTE], "ano": ["2026"], "mes": ["Janeiro"], "realizado": [100.0],
    }), ARQUIVO_CUSTOS)
    salvar_horas(pd.DataFrame({
        "c_custo": [PROJETO_TESTE], "nome": ["Colaborador Teste"], "periodo": ["01/01/2026"], "hs_nor": [8.0],
    }), ARQUIVO_HORAS)
    salvar_orcamento(
        projeto=PROJETO_TESTE, orcamento_previsto=1000.0, status_projeto="Viabilizado",
        data_inicio=None, prev_viabilidade=None, prev_qualidade=None,
        prev_aprov_lancamento=None, prev_lancamento=None, real_viabilidade=None,
        real_qualidade=None, real_aprov_lancamento=None, real_lancamento=None,
    )
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 1000.0, "anual")


def test_deletar_projeto_completo_remove_tudo_do_projeto():
    _popular_projeto_teste()
    resultado = deletar_projeto_completo(PROJETO_TESTE)
    assert resultado["custos"] == 1
    assert resultado["horas"] == 1
    assert resultado["orcamento"] == 1

    assert carregar_orcamento_projeto(PROJETO_TESTE) is None
    assert carregar_previsoes_projeto(PROJETO_TESTE).empty
    assert (carregar_custos()["centro_de_custo"] == PROJETO_TESTE).sum() == 0
    assert (carregar_horas()["c_custo"] == PROJETO_TESTE).sum() == 0


def test_limpar_tudo_esvazia_todas_as_tabelas():
    # ATENCAO: limpar_tudo() apaga TODAS as linhas das 4 tabelas, não só as
    # de teste. Só execute este teste contra um banco Supabase dedicado ao
    # desenvolvimento deste app, sem dados de produção reais.
    _popular_projeto_teste()
    limpar_tudo()
    assert carregar_custos().empty
    assert carregar_horas().empty
    assert carregar_previsoes_projeto(PROJETO_TESTE).empty
