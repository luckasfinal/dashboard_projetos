from utils.db import (
    salvar_orcamento, carregar_orcamento_projeto, carregar_orcamentos,
    deletar_orcamento_projeto,
)

PROJETO_TESTE = "PROJ__teste_pytest__"


def _salvar_orcamento_exemplo(orcamento=5000.0, status="Viabilizado"):
    salvar_orcamento(
        projeto=PROJETO_TESTE,
        orcamento_previsto=orcamento,
        status_projeto=status,
        data_inicio="2026-01-01",
        prev_viabilidade="2026-02-01",
        prev_qualidade=None,
        prev_aprov_lancamento=None,
        prev_lancamento="2026-06-01",
        real_viabilidade=None,
        real_qualidade=None,
        real_aprov_lancamento=None,
        real_lancamento=None,
        nome_projeto_editado="Projeto de Teste",
    )


def test_salvar_e_carregar_orcamento():
    _salvar_orcamento_exemplo()
    dados = carregar_orcamento_projeto(PROJETO_TESTE)
    assert dados is not None
    assert dados["projeto"] == PROJETO_TESTE
    assert float(dados["orcamento_previsto"]) == 5000.0
    assert dados["status_projeto"] == "Viabilizado"
    assert dados["nome_projeto_editado"] == "Projeto de Teste"
    assert dados["data_inicio"] == "2026-01-01"


def test_salvar_orcamento_e_upsert():
    _salvar_orcamento_exemplo(orcamento=5000.0, status="Viabilizado")
    _salvar_orcamento_exemplo(orcamento=7500.0, status="Lançado")

    dados = carregar_orcamento_projeto(PROJETO_TESTE)
    assert float(dados["orcamento_previsto"]) == 7500.0
    assert dados["status_projeto"] == "Lançado"

    todos = carregar_orcamentos()
    assert (todos["projeto"] == PROJETO_TESTE).sum() == 1  # upsert, não duplica


def test_deletar_orcamento_projeto():
    _salvar_orcamento_exemplo()
    removido = deletar_orcamento_projeto(PROJETO_TESTE)
    assert removido is True
    assert carregar_orcamento_projeto(PROJETO_TESTE) is None
