import sys
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in [str(ROOT), str(ROOT / "utils")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from utils.dashboard_executivo import (
    calcular_proximos_marcos,
    calcular_marcos_vencidos,
    calcular_kpis_home,
)


# ── helper ─────────────────────────────────────────────────────────────
def _df_proj(**overrides):
    base = {
        "projeto": ["P001"],
        "nome_projeto": ["Projeto Teste"],
        "orcamento": [0.0],
        "valor_total": [0.0],
        "pct_orcamento": [0.0],
        "prev_viabilidade": [None],      "real_viabilidade": [None],
        "prev_qualidade": [None],        "real_qualidade": [None],
        "prev_aprov_lancamento": [None], "real_aprov_lancamento": [None],
        "prev_lancamento": [None],       "real_lancamento": [None],
    }
    base.update({k: [v] for k, v in overrides.items()})
    return pd.DataFrame(base)


def _risco(nivel="baixo", pct=50.0, orc=100_000.0, atraso=0):
    return pd.DataFrame([{
        "projeto": "P001", "nome_projeto": "Projeto Teste",
        "nivel_risco": nivel, "pct_projetado": pct,
        "orcamento": orc, "dias_atraso_max": atraso,
    }])


# ── calcular_proximos_marcos ────────────────────────────────────────────

def test_proximos_marcos_dentro_de_7_dias():
    em_5 = (date.today() + timedelta(days=5)).isoformat()
    result = calcular_proximos_marcos(_df_proj(prev_lancamento=em_5), dias=7)
    assert len(result) == 1
    assert result.iloc[0]["Projeto"] == "Projeto Teste"
    assert result.iloc[0]["Dias Restantes"] == 5


def test_proximos_marcos_no_limite_7_dias_inclui():
    em_7 = (date.today() + timedelta(days=7)).isoformat()
    result = calcular_proximos_marcos(_df_proj(prev_lancamento=em_7), dias=7)
    assert len(result) == 1


def test_proximos_marcos_alem_do_limite_nao_aparece():
    em_10 = (date.today() + timedelta(days=10)).isoformat()
    result = calcular_proximos_marcos(_df_proj(prev_lancamento=em_10), dias=7)
    assert result.empty


def test_proximos_marcos_com_real_nao_aparece():
    em_3  = (date.today() + timedelta(days=3)).isoformat()
    hoje  = date.today().isoformat()
    result = calcular_proximos_marcos(
        _df_proj(prev_lancamento=em_3, real_lancamento=hoje), dias=7
    )
    assert result.empty


def test_proximos_marcos_vencido_nao_aparece():
    ontem = (date.today() - timedelta(days=1)).isoformat()
    result = calcular_proximos_marcos(_df_proj(prev_lancamento=ontem), dias=7)
    assert result.empty


def test_proximos_marcos_colunas():
    em_2 = (date.today() + timedelta(days=2)).isoformat()
    result = calcular_proximos_marcos(_df_proj(prev_viabilidade=em_2), dias=7)
    assert set(result.columns) == {"Projeto", "Marco", "Data Prevista", "Dias Restantes"}


def test_proximos_marcos_ordenado_por_dias_restantes():
    em_1 = (date.today() + timedelta(days=1)).isoformat()
    em_5 = (date.today() + timedelta(days=5)).isoformat()
    df = pd.DataFrame({
        "projeto": ["P001", "P002"],
        "nome_projeto": ["Proj 1", "Proj 2"],
        "orcamento": [0.0, 0.0], "valor_total": [0.0, 0.0], "pct_orcamento": [0.0, 0.0],
        "prev_viabilidade": [em_5, em_1], "real_viabilidade": [None, None],
        "prev_qualidade": [None, None],   "real_qualidade": [None, None],
        "prev_aprov_lancamento": [None, None], "real_aprov_lancamento": [None, None],
        "prev_lancamento": [None, None],  "real_lancamento": [None, None],
    })
    result = calcular_proximos_marcos(df, dias=7)
    assert result.iloc[0]["Dias Restantes"] == 1
    assert result.iloc[1]["Dias Restantes"] == 5


def test_proximos_marcos_todos_os_4_tipos():
    em_3 = (date.today() + timedelta(days=3)).isoformat()
    df = _df_proj(
        prev_viabilidade=em_3, prev_qualidade=em_3,
        prev_aprov_lancamento=em_3, prev_lancamento=em_3,
    )
    result = calcular_proximos_marcos(df, dias=7)
    assert len(result) == 4
    assert set(result["Marco"]) == {"Viabilidade", "Qualidade", "Aprov. Lançamento", "Lançamento"}


# ── calcular_marcos_vencidos ────────────────────────────────────────────

def test_marcos_vencidos_aparece():
    ha_5 = (date.today() - timedelta(days=5)).isoformat()
    result = calcular_marcos_vencidos(_df_proj(prev_lancamento=ha_5))
    assert len(result) == 1
    assert result.iloc[0]["Dias de Atraso"] == 5


def test_marcos_vencidos_futuro_nao_e_vencido():
    em_3 = (date.today() + timedelta(days=3)).isoformat()
    result = calcular_marcos_vencidos(_df_proj(prev_lancamento=em_3))
    assert result.empty


def test_marcos_vencidos_com_real_nao_e_vencido():
    ha_5 = (date.today() - timedelta(days=5)).isoformat()
    hoje = date.today().isoformat()
    result = calcular_marcos_vencidos(_df_proj(prev_lancamento=ha_5, real_lancamento=hoje))
    assert result.empty


def test_marcos_vencidos_colunas():
    ha_1 = (date.today() - timedelta(days=1)).isoformat()
    result = calcular_marcos_vencidos(_df_proj(prev_qualidade=ha_1))
    assert set(result.columns) == {"Projeto", "Marco", "Data Prevista", "Dias de Atraso"}


def test_marcos_vencidos_ordenado_decrescente():
    ha_1  = (date.today() - timedelta(days=1)).isoformat()
    ha_10 = (date.today() - timedelta(days=10)).isoformat()
    df = pd.DataFrame({
        "projeto": ["P001", "P002"], "nome_projeto": ["Proj 1", "Proj 2"],
        "orcamento": [0.0, 0.0], "valor_total": [0.0, 0.0], "pct_orcamento": [0.0, 0.0],
        "prev_viabilidade": [ha_1, ha_10], "real_viabilidade": [None, None],
        "prev_qualidade": [None, None],    "real_qualidade": [None, None],
        "prev_aprov_lancamento": [None, None], "real_aprov_lancamento": [None, None],
        "prev_lancamento": [None, None],   "real_lancamento": [None, None],
    })
    result = calcular_marcos_vencidos(df)
    assert result.iloc[0]["Dias de Atraso"] == 10
    assert result.iloc[1]["Dias de Atraso"] == 1


# ── calcular_kpis_home ──────────────────────────────────────────────────

def test_kpis_home_contagens_risco():
    df = _df_proj(orcamento=1000.0, valor_total=500.0, pct_orcamento=50.0)
    risco = pd.DataFrame([
        {"projeto": "P001", "nivel_risco": "alto",  "pct_projetado": 120.0, "orcamento": 1000.0, "dias_atraso_max": 10},
        {"projeto": "P002", "nivel_risco": "medio", "pct_projetado": 85.0,  "orcamento": 500.0,  "dias_atraso_max": 0},
        {"projeto": "P003", "nivel_risco": "baixo", "pct_projetado": 40.0,  "orcamento": 200.0,  "dias_atraso_max": 0},
    ])
    result = calcular_kpis_home(df, risco)
    assert result["n_ativos"] == 1
    assert result["n_alto_risco"] == 1
    assert result["n_medio_risco"] == 1
    assert result["n_baixo_risco"] == 1


def test_kpis_home_exposicao_financeira():
    # pct_projetado=120 com orcamento=1000 → exposição = 1000*(1.2-1) = 200
    result = calcular_kpis_home(_df_proj(), pd.DataFrame([{
        "projeto": "P001", "nivel_risco": "alto",
        "pct_projetado": 120.0, "orcamento": 1000.0, "dias_atraso_max": 0,
    }]))
    assert result["exposicao_financeira"] == pytest.approx(200.0)


def test_kpis_home_sem_estouro_exposicao_zero():
    result = calcular_kpis_home(_df_proj(), _risco(nivel="baixo", pct=80.0, orc=1000.0))
    assert result["exposicao_financeira"] == pytest.approx(0.0)


def test_kpis_home_consumo_medio():
    df = _df_proj(orcamento=1000.0, valor_total=750.0, pct_orcamento=75.0)
    result = calcular_kpis_home(df, _risco())
    assert result["consumo_medio_pct"] == pytest.approx(75.0)


def test_kpis_home_consumo_medio_sem_orcamento_e_zero():
    df = _df_proj(orcamento=0.0, pct_orcamento=0.0)
    result = calcular_kpis_home(df, _risco())
    assert result["consumo_medio_pct"] == pytest.approx(0.0)


def test_kpis_home_atraso_medio():
    risco = pd.DataFrame([
        {"projeto": "P001", "nivel_risco": "alto",  "pct_projetado": 90.0, "orcamento": 1000.0, "dias_atraso_max": 20},
        {"projeto": "P002", "nivel_risco": "baixo", "pct_projetado": 50.0, "orcamento": 500.0,  "dias_atraso_max": 0},
    ])
    result = calcular_kpis_home(_df_proj(), risco)
    assert result["atraso_medio_dias"] == pytest.approx(10.0)


def test_kpis_home_risco_vazio():
    result = calcular_kpis_home(_df_proj(), pd.DataFrame())
    assert result["n_alto_risco"] == 0
    assert result["n_medio_risco"] == 0
    assert result["n_baixo_risco"] == 0
    assert result["exposicao_financeira"] == 0.0
    assert result["atraso_medio_dias"] == 0.0
