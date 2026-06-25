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


# ─────────────────────────────────────────────
# Task 3: calcular_burn_rate
# ─────────────────────────────────────────────
from utils.dashboard_executivo import calcular_burn_rate


def test_calcular_burn_rate_vazio():
    result = calcular_burn_rate(pd.DataFrame())
    assert result.empty


def test_calcular_burn_rate_um_mes():
    df = pd.DataFrame({
        "centro_de_custo": ["P001", "P001"],
        "mes_ref": ["2026-01", "2026-01"],
        "realizado": [10000.0, 5000.0],
    })
    result = calcular_burn_rate(df)
    assert len(result) == 1
    row = result.iloc[0]
    assert row["custo_mensal"] == pytest.approx(15000.0)
    assert row["custo_acumulado"] == pytest.approx(15000.0)
    assert row["burn_rate"] == pytest.approx(15000.0)


def test_calcular_burn_rate_dois_meses():
    df = pd.DataFrame({
        "centro_de_custo": ["P001", "P001"],
        "mes_ref": ["2026-01", "2026-02"],
        "realizado": [10000.0, 20000.0],
    })
    result = calcular_burn_rate(df).sort_values("mes_ref")
    assert result.iloc[1]["custo_acumulado"] == pytest.approx(30000.0)
    assert result.iloc[1]["burn_rate"] == pytest.approx(15000.0)


def test_calcular_burn_rate_sem_mes_ref():
    df = pd.DataFrame({"centro_de_custo": ["P001"], "realizado": [1000.0]})
    result = calcular_burn_rate(df)
    assert result.empty


# ─────────────────────────────────────────────
# Task 4: calcular_forecast_prazo, calcular_forecast_custo, calcular_matriz_prazo_custo
# ─────────────────────────────────────────────
from utils.dashboard_executivo import (
    calcular_forecast_prazo, calcular_forecast_custo, calcular_matriz_prazo_custo,
)

# ── forecast prazo ──
def test_forecast_prazo_sem_atraso():
    df_f = _df_proj(prev_lancamento="2026-06-01",
                    prev_viabilidade="2026-01-01", real_viabilidade="2026-01-01")
    df_marcos = calcular_marcos(df_f)
    result = calcular_forecast_prazo(df_f, df_marcos)
    row = result.iloc[0]
    assert row["atraso_medio_dias"] == 0
    assert str(row["forecast"]) == "2026-06-01"

def test_forecast_prazo_com_atraso_10dias():
    df_f = _df_proj(prev_lancamento="2026-06-01",
                    prev_viabilidade="2026-01-01", real_viabilidade="2026-01-11")
    df_marcos = calcular_marcos(df_f)
    result = calcular_forecast_prazo(df_f, df_marcos)
    row = result.iloc[0]
    assert row["atraso_medio_dias"] == 10
    assert str(row["forecast"]) == "2026-06-11"

def test_forecast_prazo_sem_lancamento_previsto():
    df_f = _df_proj()
    df_marcos = calcular_marcos(df_f)
    result = calcular_forecast_prazo(df_f, df_marcos)
    assert result.iloc[0]["forecast"] is None

# ── forecast custo (EAC) ──
def test_forecast_custo_pct_zero_retorna_none():
    df_f = _df_proj()
    df_f["valor_total"] = 50000.0
    df_f["orcamento"] = 100000.0
    df_marcos = calcular_marcos(df_f)
    result = calcular_forecast_custo(df_f, df_marcos)
    assert result.iloc[0]["eac"] is None

def test_forecast_custo_eac_calculado():
    # Viabilidade concluída = 45% → EAC = 50000 / 0.45
    df_f = _df_proj(prev_viabilidade="2026-01-01", real_viabilidade="2026-01-05")
    df_f["valor_total"] = 50000.0
    df_f["orcamento"] = 100000.0
    df_marcos = calcular_marcos(df_f)
    result = calcular_forecast_custo(df_f, df_marcos)
    row = result.iloc[0]
    assert row["eac"] == pytest.approx(50000 / 0.45, rel=1e-3)

def test_forecast_custo_desvio_positivo_quando_estouro():
    df_f = _df_proj(prev_viabilidade="2026-01-01", real_viabilidade="2026-01-01")
    df_f["valor_total"] = 90000.0
    df_f["orcamento"] = 100000.0
    df_marcos = calcular_marcos(df_f)
    result = calcular_forecast_custo(df_f, df_marcos)
    # EAC = 90000/0.45 = 200000 > 100000 → desvio > 0
    assert result.iloc[0]["desvio_eac_pct"] > 0

# ── matriz ──
def test_calcular_matriz_quadrante_controlado():
    df_fp = pd.DataFrame([{"nome_projeto": "A", "data_planejada": None,
                            "atraso_medio_dias": 0, "forecast": None, "desvio_total": -5}])
    df_fc = pd.DataFrame([{"nome_projeto": "A", "custo_atual": 0, "pct_concluido": 0.5,
                            "eac": 80000.0, "orcamento": 100000.0, "desvio_eac_pct": -20.0}])
    result = calcular_matriz_prazo_custo(df_fp, df_fc)
    assert result.iloc[0]["quadrante"] == "Controlado"

def test_calcular_matriz_quadrante_critico():
    df_fp = pd.DataFrame([{"nome_projeto": "B", "data_planejada": None,
                            "atraso_medio_dias": 30, "forecast": None, "desvio_total": 30}])
    df_fc = pd.DataFrame([{"nome_projeto": "B", "custo_atual": 0, "pct_concluido": 0.5,
                            "eac": 120000.0, "orcamento": 100000.0, "desvio_eac_pct": 20.0}])
    result = calcular_matriz_prazo_custo(df_fp, df_fc)
    assert result.iloc[0]["quadrante"] == "Crítico"

def test_calcular_matriz_vazio_sem_eac():
    df_fp = pd.DataFrame([{"nome_projeto": "C", "desvio_total": 5}])
    df_fc = pd.DataFrame([{"nome_projeto": "C", "desvio_eac_pct": None}])
    result = calcular_matriz_prazo_custo(df_fp, df_fc)
    assert result.empty


# ─────────────────────────────────────────────
# Task 5: calcular_resumo_executivo, calcular_status_projetos,
#         calcular_custos_por_categoria, calcular_recursos
# ─────────────────────────────────────────────
from utils.dashboard_executivo import (
    calcular_resumo_executivo, calcular_status_projetos,
    calcular_custos_por_categoria, calcular_recursos,
)

def _df_custos(projeto="P001", conta="610000 - Mão de Obra", valor=10000.0, mes="2026-01"):
    return pd.DataFrame({
        "centro_de_custo": [projeto], "conta": [conta],
        "realizado": [valor], "mes_ref": [mes],
    })

def _df_horas(projeto="P001", colaborador="Ana", horas=80.0):
    return pd.DataFrame({
        "c_custo": [projeto], "nome": [colaborador], "hs_nor": [horas],
    })

# ── resumo executivo ──
def test_resumo_executivo_projetos_ativos():
    df_f = _df_proj()
    df_f["status_projeto"] = "Viabilizado"
    df_marcos = calcular_marcos(df_f)
    r = calcular_resumo_executivo(df_f, _df_custos(), _df_horas(), df_marcos)
    assert r["projetos_ativos"] == 1

def test_resumo_executivo_projeto_cancelado_nao_conta():
    df_f = _df_proj()
    df_f["status_projeto"] = "Cancelado"
    df_marcos = calcular_marcos(df_f)
    r = calcular_resumo_executivo(df_f, pd.DataFrame(), pd.DataFrame(), df_marcos)
    assert r["projetos_ativos"] == 0

def test_resumo_executivo_horas_e_custos():
    df_f = _df_proj()
    df_marcos = calcular_marcos(df_f)
    r = calcular_resumo_executivo(df_f, _df_custos(valor=5000.0), _df_horas(horas=40.0), df_marcos)
    assert r["horas_consumidas"] == pytest.approx(40.0)
    assert r["custos_acumulados"] == pytest.approx(5000.0)

def test_resumo_executivo_pct_medio_zero_sem_marcos():
    df_f = _df_proj()
    df_marcos = calcular_marcos(df_f)
    r = calcular_resumo_executivo(df_f, pd.DataFrame(), pd.DataFrame(), df_marcos)
    assert r["pct_medio_conclusao"] == pytest.approx(0.0)

# ── status projetos ──
def test_status_projetos_colunas():
    df_f = _df_proj()
    df_f["status_projeto"] = "Viabilizado"
    df_marcos = calcular_marcos(df_f)
    result = calcular_status_projetos(df_f, df_marcos, pd.DataFrame(), pd.DataFrame())
    assert "pct_concluido" in result.columns
    assert "marcos_concluidos" in result.columns
    assert "marcos_totais" in result.columns
    assert result.iloc[0]["marcos_totais"] == 4

def test_status_projetos_status_visual_verde():
    df_f = _df_proj()
    df_f["status_projeto"] = "Viabilizado"
    df_marcos = calcular_marcos(df_f)
    result = calcular_status_projetos(df_f, df_marcos, pd.DataFrame(), pd.DataFrame())
    assert result.iloc[0]["status_visual"] == "🟢"

# ── custos por categoria ──
def test_calcular_custos_por_categoria_vazio():
    result = calcular_custos_por_categoria(pd.DataFrame())
    assert result.empty

def test_calcular_custos_por_categoria_agrupa():
    df = pd.DataFrame({
        "centro_de_custo": ["P001", "P001"],
        "conta": ["610000 - Mão de Obra", "610001 - Salário"],
        "realizado": [1000.0, 2000.0],
    })
    result = calcular_custos_por_categoria(df)
    row = result[result["categoria_custo"] == "Mão de obra"].iloc[0]
    assert row["total_custo"] == pytest.approx(3000.0)

# ── recursos ──
def test_calcular_recursos_vazio():
    df_f = _df_proj()
    result = calcular_recursos(df_f, pd.DataFrame())
    assert result.empty

def test_calcular_recursos_horas_por_colaborador():
    df_f = _df_proj()
    df_horas = pd.DataFrame({
        "c_custo": ["P001", "P001"],
        "nome": ["Ana", "João"],
        "hs_nor": [80.0, 40.0],
    })
    result = calcular_recursos(df_f, df_horas)
    row = result.iloc[0]
    assert row["horas_total"] == pytest.approx(120.0)
    assert row["n_colaboradores"] == 2
    assert row["horas_por_colaborador"] == pytest.approx(60.0)
