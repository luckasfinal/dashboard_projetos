from datetime import date, timedelta

import pandas as pd

from utils.data_processor import calcular_risco_portfolio


def _data(dias_a_partir_de_hoje: int) -> str:
    return (date.today() + timedelta(days=dias_a_partir_de_hoje)).strftime("%Y-%m-%d")


def _mes_ref(meses_atras: int) -> str:
    hoje = date.today()
    total = hoje.month - 1 - meses_atras
    ano = hoje.year + total // 12
    mes = total % 12 + 1
    return f"{ano}-{mes:02d}"


def _data_em_meses(n_meses: int) -> str:
    hoje = date.today()
    total = hoje.month - 1 + n_meses
    ano = hoje.year + total // 12
    mes = total % 12 + 1
    return date(ano, mes, 15).strftime("%Y-%m-%d")


def _linha_projeto(projeto, nome, valor_total, orcamento, **marcos):
    base = {
        "projeto": projeto, "nome_projeto": nome,
        "valor_total": valor_total, "orcamento": orcamento,
        "prev_viabilidade": None, "real_viabilidade": None,
        "prev_qualidade": None, "real_qualidade": None,
        "prev_aprov_lancamento": None, "real_aprov_lancamento": None,
        "prev_lancamento": None, "real_lancamento": None,
    }
    base.update(marcos)
    return base


def test_projeto_saudavel_e_baixo_risco():
    df = pd.DataFrame([_linha_projeto("P001", "Projeto Saudável", 4000, 10000)])
    df_custos_raw = pd.DataFrame(columns=["centro_de_custo", "mes_ref", "realizado"])

    risco = calcular_risco_portfolio(df, df_custos_raw)

    assert risco.iloc[0]["nivel_risco"] == "baixo"
    assert risco.iloc[0]["motivos"] == []


def test_projecao_de_estouro_classifica_como_alto_mesmo_sem_estourar_ainda():
    # Realizado (6000) ainda é só 60% do orçamento (10000), mas o ritmo de gasto
    # (3000/mês por 2 meses) projetado para os próximos 2 meses até o lançamento
    # estoura o orçamento (6000 + 3000*2 = 12000 = 120%).
    df = pd.DataFrame([_linha_projeto(
        "P002", "Projeto Vai Estourar", 6000, 10000,
        prev_lancamento=_data_em_meses(2),
    )])
    df_custos_raw = pd.DataFrame([
        {"centro_de_custo": "P002", "mes_ref": _mes_ref(1), "realizado": 3000},
        {"centro_de_custo": "P002", "mes_ref": _mes_ref(0), "realizado": 3000},
    ])

    risco = calcular_risco_portfolio(df, df_custos_raw)

    assert risco.iloc[0]["nivel_risco"] == "alto"
    assert any("Projeção de custo" in m for m in risco.iloc[0]["motivos"])


def test_projecao_entre_80_e_100_e_risco_medio():
    df = pd.DataFrame([_linha_projeto("P003", "Projeto Atenção", 8500, 10000)])
    df_custos_raw = pd.DataFrame(columns=["centro_de_custo", "mes_ref", "realizado"])

    risco = calcular_risco_portfolio(df, df_custos_raw)

    assert risco.iloc[0]["nivel_risco"] == "medio"


def test_marco_atrasado_classifica_como_alto_mesmo_com_custo_saudavel():
    df = pd.DataFrame([_linha_projeto(
        "P004", "Projeto Atrasado", 1000, 10000,
        prev_qualidade=_data(-10),  # previsto há 10 dias, sem real ainda
    )])
    df_custos_raw = pd.DataFrame(columns=["centro_de_custo", "mes_ref", "realizado"])

    risco = calcular_risco_portfolio(df, df_custos_raw)

    assert risco.iloc[0]["nivel_risco"] == "alto"
    assert risco.iloc[0]["dias_atraso_max"] == 10
    assert any("Qualidade" in m and "10" in m for m in risco.iloc[0]["motivos"])


def test_projeto_sem_orcamento_e_baixo_risco_com_motivo_informativo():
    df = pd.DataFrame([_linha_projeto("P005", "Projeto Sem Orçamento", 1000, 0)])
    df_custos_raw = pd.DataFrame(columns=["centro_de_custo", "mes_ref", "realizado"])

    risco = calcular_risco_portfolio(df, df_custos_raw)

    assert risco.iloc[0]["nivel_risco"] == "baixo"
    assert risco.iloc[0]["pct_projetado"] is None
    assert "Sem orçamento cadastrado" in risco.iloc[0]["motivos"]


def test_ordena_por_nivel_de_risco_alto_primeiro():
    df = pd.DataFrame([
        _linha_projeto("P010", "Baixo", 1000, 10000),
        _linha_projeto("P011", "Alto", 11000, 10000),
        _linha_projeto("P012", "Médio", 8500, 10000),
    ])
    df_custos_raw = pd.DataFrame(columns=["centro_de_custo", "mes_ref", "realizado"])

    risco = calcular_risco_portfolio(df, df_custos_raw)

    assert risco["nivel_risco"].tolist() == ["alto", "medio", "baixo"]
