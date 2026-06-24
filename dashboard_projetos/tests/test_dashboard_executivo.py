import pytest
import pandas as pd
from utils.dashboard_executivo import (
    categorizar_conta, PALAVRAS_CATEGORIA, CATEGORIAS_CUSTO,
)

def test_categorizar_conta_mao_de_obra():
    assert categorizar_conta("610000 - Mão de Obra Própria") == "Mão de obra"

def test_categorizar_conta_terceiros():
    assert categorizar_conta("720100 - Serviços de Terceiros") == "Terceiros"

def test_categorizar_conta_materiais():
    assert categorizar_conta("510000 - Material de Consumo") == "Materiais"

def test_categorizar_conta_viagens():
    assert categorizar_conta("840000 - Viagem e Hospedagem") == "Viagens"

def test_categorizar_conta_fallback_outras():
    assert categorizar_conta("999999 - Despesas Diversas") == "Outras"

def test_categorizar_conta_vazia():
    assert categorizar_conta("") == "Outras"

def test_categorizar_conta_none():
    assert categorizar_conta(None) == "Outras"

def test_categorizar_conta_case_insensitive():
    assert categorizar_conta("MÃO DE OBRA INDIRETA") == "Mão de obra"

def test_categorias_custo_lista():
    assert set(CATEGORIAS_CUSTO) == {"Mão de obra", "Terceiros", "Materiais", "Viagens"}


# ─────────────────────────────────────────────
# Task 2: calcular_marcos
# ─────────────────────────────────────────────
from utils.dashboard_executivo import calcular_marcos, MARCOS_CONFIG


def _df_proj(**overrides):
    base = {
        "projeto": ["P001"], "nome_projeto": ["Projeto Teste"],
        "prev_viabilidade": [None], "real_viabilidade": [None],
        "prev_qualidade": [None], "real_qualidade": [None],
        "prev_aprov_lancamento": [None], "real_aprov_lancamento": [None],
        "prev_lancamento": [None], "real_lancamento": [None],
    }
    base.update({k: [v] for k, v in overrides.items()})
    return pd.DataFrame(base)


def test_calcular_marcos_retorna_4_linhas():
    assert len(calcular_marcos(_df_proj())) == 4


def test_calcular_marcos_pesos_somam_1():
    assert abs(sum(cfg[3] for cfg in MARCOS_CONFIG) - 1.0) < 1e-9


def test_calcular_marcos_viabilidade_peso():
    result = calcular_marcos(_df_proj())
    assert result[result["marco"] == "Viabilidade"]["peso"].iloc[0] == pytest.approx(0.45)


def test_calcular_marcos_qualidade_peso():
    result = calcular_marcos(_df_proj())
    assert result[result["marco"] == "Qualidade"]["peso"].iloc[0] == pytest.approx(0.40)


def test_calcular_marcos_aprov_peso():
    result = calcular_marcos(_df_proj())
    assert result[result["marco"] == "Aprovação p/ Lançamento"]["peso"].iloc[0] == pytest.approx(0.05)


def test_calcular_marcos_lancamento_peso():
    result = calcular_marcos(_df_proj())
    assert result[result["marco"] == "Lançamento"]["peso"].iloc[0] == pytest.approx(0.10)


def test_calcular_marcos_sem_datas_pendente():
    result = calcular_marcos(_df_proj())
    assert (result["status_marco"] == "Pendente").all()
    assert not result["concluido"].any()


def test_calcular_marcos_concluido_no_prazo():
    result = calcular_marcos(_df_proj(prev_viabilidade="2026-01-15", real_viabilidade="2026-01-10"))
    row = result[result["marco"] == "Viabilidade"].iloc[0]
    assert row["concluido"] is True
    assert row["status_marco"] == "Concluído"
    assert row["desvio_dias"] == -5


def test_calcular_marcos_concluido_atrasado():
    result = calcular_marcos(_df_proj(prev_viabilidade="2026-01-01", real_viabilidade="2026-01-11"))
    row = result[result["marco"] == "Viabilidade"].iloc[0]
    assert row["status_marco"] == "Atrasado"
    assert row["desvio_dias"] == 10


def test_calcular_marcos_pct_parcial():
    result = calcular_marcos(_df_proj(
        prev_viabilidade="2026-01-01", real_viabilidade="2026-01-05",
        prev_qualidade="2026-03-01",   real_qualidade="2026-03-01",
    ))
    assert result[result["concluido"]]["peso"].sum() == pytest.approx(0.85)


def test_calcular_marcos_todos_concluidos():
    result = calcular_marcos(_df_proj(
        prev_viabilidade="2026-01-01", real_viabilidade="2026-01-05",
        prev_qualidade="2026-03-01",   real_qualidade="2026-03-01",
        prev_aprov_lancamento="2026-05-01", real_aprov_lancamento="2026-05-02",
        prev_lancamento="2026-06-01",  real_lancamento="2026-06-01",
    ))
    assert result[result["concluido"]]["peso"].sum() == pytest.approx(1.0)
