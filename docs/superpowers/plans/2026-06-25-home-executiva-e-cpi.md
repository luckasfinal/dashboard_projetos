# Home Executiva + CPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar uma Home Executiva como tela inicial do sistema e adicionar o CPI (Cost Performance Index) como indicador de eficiência de custo em todas as telas relevantes.

**Architecture:** Cinco novas funções puras adicionadas a `dashboard_executivo.py` (sem Streamlit) cobrem toda a lógica de negócio nova; a página `home.py` e as edições nas páginas existentes consomem essas funções. O CPI é calculado como BCWP/ACWP = (Orçamento × % Marcos Concluídos) / Custo Real.

**Tech Stack:** Python 3.11+, Streamlit (multi-page via st.navigation), pandas, Plotly (não usado na home), pytest, PostgreSQL/SQLAlchemy (Supabase).

## Global Constraints

- Nenhuma nova dependência Python — apenas bibliotecas já instaladas.
- Todos os novos cálculos devem ser funções puras em `dashboard_executivo.py` (sem imports de Streamlit).
- Seguir o padrão de testes existente: `conftest.py` com `_preparar_schema` + `_limpar_dados_de_teste` autouse. Testes novos não tocam no banco — apenas usam DataFrames em memória.
- Navegação entre páginas usa `st.switch_page(str(_ROOT / "pages" / "X.py"))` — padrão já usado em `4_visao_executiva.py`.
- `_df_proj(**overrides)` é um helper local definido em cada arquivo de teste que precisa dele (não está no conftest).
- Strings de data no formato `"YYYY-MM-DD"`.
- Comandos de teste executados em: `dashboard_projetos/` (diretório raiz do projeto, onde está `utils/`).

---

## File Map

### New
- `dashboard_projetos/pages/home.py` — página Home Executiva
- `dashboard_projetos/tests/test_home_executiva.py` — testes das funções de home

### Modified
- `dashboard_projetos/utils/dashboard_executivo.py` — adicionar `_cpi`, `calcular_cpi_projeto`, `calcular_proximos_marcos`, `calcular_marcos_vencidos`, `calcular_kpis_home`; atualizar `calcular_forecast_custo` para incluir coluna `cpi`
- `dashboard_projetos/app.py` — adicionar grupo "🏠 Início" com `home.py` como primeira página
- `dashboard_projetos/pages/5_dashboard_executivo.py` — exibir coluna CPI na tabela EAC; adicionar caption explicativo
- `dashboard_projetos/pages/3_projetos.py` — exibir CPI no painel de KPIs do Detalhamento
- `dashboard_projetos/tests/test_dashboard_executivo.py` — adicionar testes de CPI

---

## Task 1: Funções de home backend + testes

**Files:**
- Modify: `dashboard_projetos/utils/dashboard_executivo.py` — adicionar as 3 funções de home
- Create: `dashboard_projetos/tests/test_home_executiva.py`

**Interfaces:**
- Produces:
  - `calcular_proximos_marcos(df_f: pd.DataFrame, dias: int = 7) -> pd.DataFrame` — colunas: `Projeto`, `Marco`, `Data Prevista`, `Dias Restantes`
  - `calcular_marcos_vencidos(df_f: pd.DataFrame) -> pd.DataFrame` — colunas: `Projeto`, `Marco`, `Data Prevista`, `Dias de Atraso`
  - `calcular_kpis_home(df_dashboard: pd.DataFrame, risco: pd.DataFrame) -> dict` — chaves: `n_ativos`, `n_alto_risco`, `n_medio_risco`, `n_baixo_risco`, `exposicao_financeira`, `consumo_medio_pct`, `atraso_medio_dias`

- [ ] **Step 1: Escrever os testes que falham**

Criar `dashboard_projetos/tests/test_home_executiva.py` com o conteúdo abaixo:

```python
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
    em_5_dias = (date.today() + timedelta(days=5)).isoformat()
    df = _df_proj(prev_lancamento=em_5_dias)
    result = calcular_proximos_marcos(df, dias=7)
    assert len(result) == 1
    assert result.iloc[0]["Projeto"] == "Projeto Teste"
    assert result.iloc[0]["Dias Restantes"] == 5


def test_proximos_marcos_no_limite_7_dias_inclui():
    em_7_dias = (date.today() + timedelta(days=7)).isoformat()
    df = _df_proj(prev_lancamento=em_7_dias)
    result = calcular_proximos_marcos(df, dias=7)
    assert len(result) == 1


def test_proximos_marcos_alem_do_limite_nao_aparece():
    em_10_dias = (date.today() + timedelta(days=10)).isoformat()
    df = _df_proj(prev_lancamento=em_10_dias)
    result = calcular_proximos_marcos(df, dias=7)
    assert result.empty


def test_proximos_marcos_com_real_nao_aparece():
    em_3_dias = (date.today() + timedelta(days=3)).isoformat()
    hoje = date.today().isoformat()
    df = _df_proj(prev_lancamento=em_3_dias, real_lancamento=hoje)
    result = calcular_proximos_marcos(df, dias=7)
    assert result.empty


def test_proximos_marcos_vencido_nao_aparece():
    ontem = (date.today() - timedelta(days=1)).isoformat()
    df = _df_proj(prev_lancamento=ontem)
    result = calcular_proximos_marcos(df, dias=7)
    assert result.empty


def test_proximos_marcos_colunas():
    em_2_dias = (date.today() + timedelta(days=2)).isoformat()
    df = _df_proj(prev_viabilidade=em_2_dias)
    result = calcular_proximos_marcos(df, dias=7)
    assert set(result.columns) == {"Projeto", "Marco", "Data Prevista", "Dias Restantes"}


def test_proximos_marcos_ordenado_por_dias_restantes():
    em_1_dia = (date.today() + timedelta(days=1)).isoformat()
    em_5_dias = (date.today() + timedelta(days=5)).isoformat()
    df = pd.DataFrame({
        "projeto": ["P001", "P002"],
        "nome_projeto": ["Proj 1", "Proj 2"],
        "orcamento": [0.0, 0.0], "valor_total": [0.0, 0.0], "pct_orcamento": [0.0, 0.0],
        "prev_viabilidade": [em_5_dias, em_1_dia], "real_viabilidade": [None, None],
        "prev_qualidade": [None, None], "real_qualidade": [None, None],
        "prev_aprov_lancamento": [None, None], "real_aprov_lancamento": [None, None],
        "prev_lancamento": [None, None], "real_lancamento": [None, None],
    })
    result = calcular_proximos_marcos(df, dias=7)
    assert result.iloc[0]["Dias Restantes"] == 1
    assert result.iloc[1]["Dias Restantes"] == 5


def test_proximos_marcos_todos_os_4_tipos_de_marco():
    em_3 = (date.today() + timedelta(days=3)).isoformat()
    df = _df_proj(
        prev_viabilidade=em_3, prev_qualidade=em_3,
        prev_aprov_lancamento=em_3, prev_lancamento=em_3,
    )
    result = calcular_proximos_marcos(df, dias=7)
    assert len(result) == 4
    assert set(result["Marco"]) == {
        "Viabilidade", "Qualidade", "Aprov. Lançamento", "Lançamento"
    }


# ── calcular_marcos_vencidos ────────────────────────────────────────────

def test_marcos_vencidos_aparece():
    ha_5_dias = (date.today() - timedelta(days=5)).isoformat()
    df = _df_proj(prev_lancamento=ha_5_dias)
    result = calcular_marcos_vencidos(df)
    assert len(result) == 1
    assert result.iloc[0]["Dias de Atraso"] == 5


def test_marcos_vencidos_futuro_nao_e_vencido():
    em_3_dias = (date.today() + timedelta(days=3)).isoformat()
    df = _df_proj(prev_lancamento=em_3_dias)
    result = calcular_marcos_vencidos(df)
    assert result.empty


def test_marcos_vencidos_com_real_nao_e_vencido():
    ha_5_dias = (date.today() - timedelta(days=5)).isoformat()
    hoje = date.today().isoformat()
    df = _df_proj(prev_lancamento=ha_5_dias, real_lancamento=hoje)
    result = calcular_marcos_vencidos(df)
    assert result.empty


def test_marcos_vencidos_colunas():
    ha_1 = (date.today() - timedelta(days=1)).isoformat()
    df = _df_proj(prev_qualidade=ha_1)
    result = calcular_marcos_vencidos(df)
    assert set(result.columns) == {"Projeto", "Marco", "Data Prevista", "Dias de Atraso"}


def test_marcos_vencidos_ordenado_decrescente():
    ha_1 = (date.today() - timedelta(days=1)).isoformat()
    ha_10 = (date.today() - timedelta(days=10)).isoformat()
    df = pd.DataFrame({
        "projeto": ["P001", "P002"],
        "nome_projeto": ["Proj 1", "Proj 2"],
        "orcamento": [0.0, 0.0], "valor_total": [0.0, 0.0], "pct_orcamento": [0.0, 0.0],
        "prev_viabilidade": [ha_1, ha_10], "real_viabilidade": [None, None],
        "prev_qualidade": [None, None], "real_qualidade": [None, None],
        "prev_aprov_lancamento": [None, None], "real_aprov_lancamento": [None, None],
        "prev_lancamento": [None, None], "real_lancamento": [None, None],
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
    assert result["n_ativos"] == 1          # tamanho do df_dashboard
    assert result["n_alto_risco"] == 1
    assert result["n_medio_risco"] == 1
    assert result["n_baixo_risco"] == 1


def test_kpis_home_exposicao_financeira():
    # pct_projetado=120 com orcamento=1000 → exposição = 1000*(1.2-1) = 200
    df = _df_proj()
    risco = pd.DataFrame([{
        "projeto": "P001", "nivel_risco": "alto",
        "pct_projetado": 120.0, "orcamento": 1000.0, "dias_atraso_max": 0,
    }])
    result = calcular_kpis_home(df, risco)
    assert result["exposicao_financeira"] == pytest.approx(200.0)


def test_kpis_home_sem_estouro_exposicao_zero():
    df = _df_proj()
    risco = _risco(nivel="baixo", pct=80.0, orc=1000.0)
    result = calcular_kpis_home(df, risco)
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
    df = _df_proj()
    risco = pd.DataFrame([
        {"projeto": "P001", "nivel_risco": "alto",  "pct_projetado": 90.0, "orcamento": 1000.0, "dias_atraso_max": 20},
        {"projeto": "P002", "nivel_risco": "baixo", "pct_projetado": 50.0, "orcamento": 500.0,  "dias_atraso_max": 0},
    ])
    result = calcular_kpis_home(df, risco)
    assert result["atraso_medio_dias"] == pytest.approx(10.0)


def test_kpis_home_risco_vazio():
    df = _df_proj()
    result = calcular_kpis_home(df, pd.DataFrame())
    assert result["n_alto_risco"] == 0
    assert result["n_medio_risco"] == 0
    assert result["n_baixo_risco"] == 0
    assert result["exposicao_financeira"] == 0.0
    assert result["atraso_medio_dias"] == 0.0
```

- [ ] **Step 2: Rodar os testes e confirmar que TODOS falham**

```
cd "C:\Users\lu051172\Onedrive - intelbras.com.br\Claude\dashboard_projetos\dashboard_projetos"
python -m pytest tests/test_home_executiva.py -v 2>&1 | head -40
```

Esperado: falha com `ImportError` em `calcular_proximos_marcos`, `calcular_marcos_vencidos`, `calcular_kpis_home`.

- [ ] **Step 3: Implementar as 3 funções em `dashboard_executivo.py`**

Adicionar ao final de `dashboard_projetos/utils/dashboard_executivo.py`, antes da última linha (se houver):

```python
# ─────────────────────────────────────────────
# Home Executiva — funções de portfólio
# ─────────────────────────────────────────────

_MARCOS_HOME: list[tuple[str, str, str]] = [
    ("prev_viabilidade",      "real_viabilidade",      "Viabilidade"),
    ("prev_qualidade",        "real_qualidade",        "Qualidade"),
    ("prev_aprov_lancamento", "real_aprov_lancamento", "Aprov. Lançamento"),
    ("prev_lancamento",       "real_lancamento",       "Lançamento"),
]


def calcular_proximos_marcos(df_f: pd.DataFrame, dias: int = 7) -> pd.DataFrame:
    """Retorna marcos com data prevista em [hoje, hoje+dias] e sem data realizada."""
    hoje = datetime.today().date()
    limite = hoje + timedelta(days=dias)
    linhas: list[dict] = []
    for _, row in df_f.iterrows():
        for col_prev, col_real, label in _MARCOS_HOME:
            prev_d = _parse_data(row.get(col_prev))
            real_d = _parse_data(row.get(col_real))
            if prev_d is not None and real_d is None and hoje <= prev_d <= limite:
                linhas.append({
                    "Projeto": row.get("nome_projeto", row.get("projeto")),
                    "Marco": label,
                    "Data Prevista": prev_d.strftime("%d/%m/%Y"),
                    "Dias Restantes": (prev_d - hoje).days,
                })
    if not linhas:
        return pd.DataFrame(columns=["Projeto", "Marco", "Data Prevista", "Dias Restantes"])
    return pd.DataFrame(linhas).sort_values("Dias Restantes").reset_index(drop=True)


def calcular_marcos_vencidos(df_f: pd.DataFrame) -> pd.DataFrame:
    """Retorna marcos com data prevista < hoje e sem data realizada."""
    hoje = datetime.today().date()
    linhas: list[dict] = []
    for _, row in df_f.iterrows():
        for col_prev, col_real, label in _MARCOS_HOME:
            prev_d = _parse_data(row.get(col_prev))
            real_d = _parse_data(row.get(col_real))
            if prev_d is not None and real_d is None and prev_d < hoje:
                linhas.append({
                    "Projeto": row.get("nome_projeto", row.get("projeto")),
                    "Marco": label,
                    "Data Prevista": prev_d.strftime("%d/%m/%Y"),
                    "Dias de Atraso": (hoje - prev_d).days,
                })
    if not linhas:
        return pd.DataFrame(columns=["Projeto", "Marco", "Data Prevista", "Dias de Atraso"])
    return pd.DataFrame(linhas).sort_values("Dias de Atraso", ascending=False).reset_index(drop=True)


def calcular_kpis_home(df_dashboard: pd.DataFrame, risco: pd.DataFrame) -> dict:
    """Retorna KPIs consolidados para a Home Executiva."""
    n_ativos = len(df_dashboard)

    if risco.empty:
        n_alto = n_medio = n_baixo = 0
        exposicao = atraso_medio = 0.0
    else:
        n_alto  = int((risco["nivel_risco"] == "alto").sum())
        n_medio = int((risco["nivel_risco"] == "medio").sum())
        n_baixo = int((risco["nivel_risco"] == "baixo").sum())
        mask_estouro = risco["pct_projetado"].notna() & (risco["pct_projetado"] > 100)
        if mask_estouro.any():
            exposicao = float(
                risco.loc[mask_estouro].apply(
                    lambda r: r["orcamento"] * (r["pct_projetado"] / 100 - 1), axis=1
                ).sum()
            )
        else:
            exposicao = 0.0
        atraso_medio = float(risco["dias_atraso_max"].mean())

    consumo_medio = 0.0
    if (
        not df_dashboard.empty
        and "orcamento" in df_dashboard.columns
        and "pct_orcamento" in df_dashboard.columns
    ):
        df_com_orc = df_dashboard[df_dashboard["orcamento"] > 0]
        if not df_com_orc.empty:
            consumo_medio = float(df_com_orc["pct_orcamento"].mean())

    return {
        "n_ativos": n_ativos,
        "n_alto_risco": n_alto,
        "n_medio_risco": n_medio,
        "n_baixo_risco": n_baixo,
        "exposicao_financeira": exposicao,
        "consumo_medio_pct": consumo_medio,
        "atraso_medio_dias": atraso_medio,
    }
```

- [ ] **Step 4: Rodar os testes e confirmar que TODOS passam**

```
python -m pytest tests/test_home_executiva.py -v
```

Esperado: todos os testes `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add dashboard_projetos/utils/dashboard_executivo.py dashboard_projetos/tests/test_home_executiva.py
git commit -m "feat: adiciona calcular_proximos_marcos, calcular_marcos_vencidos, calcular_kpis_home"
```

---

## Task 2: CPI backend + testes

**Files:**
- Modify: `dashboard_projetos/utils/dashboard_executivo.py` — adicionar `_cpi`, `calcular_cpi_projeto`; atualizar `calcular_forecast_custo`
- Modify: `dashboard_projetos/tests/test_dashboard_executivo.py` — adicionar testes de CPI

**Interfaces:**
- Produces:
  - `_cpi(custo: float, orc: float, pct: float) -> float | None` — helper interno; retorna `None` se qualquer arg for ≤ 0
  - `calcular_cpi_projeto(row: dict | pd.Series) -> float | None` — CPI para uma linha de projeto; usa `MARCOS_CONFIG` e `_parse_data`
  - `calcular_forecast_custo` atualizado: mesma assinatura de entrada, coluna `"cpi"` adicionada ao DataFrame retornado (pode ser `None` quando sem dados)

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `dashboard_projetos/tests/test_dashboard_executivo.py`:

```python
# ─────────────────────────────────────────────
# CPI — _cpi helper e calcular_cpi_projeto
# ─────────────────────────────────────────────
from utils.dashboard_executivo import calcular_cpi_projeto


def test_cpi_eficiente_gastou_menos():
    # 45% concluído (viabilidade), gastou R$400 de R$1000 → BCWP=450, CPI=450/400=1.125
    row = {
        "valor_total": 400.0, "orcamento": 1000.0,
        "prev_viabilidade": "2026-01-01", "real_viabilidade": "2026-01-05",
        "prev_qualidade": None, "real_qualidade": None,
        "prev_aprov_lancamento": None, "real_aprov_lancamento": None,
        "prev_lancamento": None, "real_lancamento": None,
    }
    result = calcular_cpi_projeto(row)
    assert result == pytest.approx(1.125, rel=1e-3)


def test_cpi_em_risco_gastou_mais():
    # 45% concluído, gastou R$700 de R$1000 → BCWP=450, CPI=450/700≈0.643
    row = {
        "valor_total": 700.0, "orcamento": 1000.0,
        "prev_viabilidade": "2026-01-01", "real_viabilidade": "2026-01-01",
        "prev_qualidade": None, "real_qualidade": None,
        "prev_aprov_lancamento": None, "real_aprov_lancamento": None,
        "prev_lancamento": None, "real_lancamento": None,
    }
    result = calcular_cpi_projeto(row)
    assert result == pytest.approx(450.0 / 700.0, rel=1e-3)


def test_cpi_exatamente_no_orcamento():
    # 45% concluído, gastou R$450 de R$1000 → CPI=1.0
    row = {
        "valor_total": 450.0, "orcamento": 1000.0,
        "prev_viabilidade": "2026-01-01", "real_viabilidade": "2026-01-01",
        "prev_qualidade": None, "real_qualidade": None,
        "prev_aprov_lancamento": None, "real_aprov_lancamento": None,
        "prev_lancamento": None, "real_lancamento": None,
    }
    result = calcular_cpi_projeto(row)
    assert result == pytest.approx(1.0)


def test_cpi_none_sem_custo():
    row = {
        "valor_total": 0.0, "orcamento": 1000.0,
        "prev_viabilidade": "2026-01-01", "real_viabilidade": "2026-01-01",
        "prev_qualidade": None, "real_qualidade": None,
        "prev_aprov_lancamento": None, "real_aprov_lancamento": None,
        "prev_lancamento": None, "real_lancamento": None,
    }
    assert calcular_cpi_projeto(row) is None


def test_cpi_none_sem_orcamento():
    row = {
        "valor_total": 500.0, "orcamento": 0.0,
        "prev_viabilidade": "2026-01-01", "real_viabilidade": "2026-01-01",
        "prev_qualidade": None, "real_qualidade": None,
        "prev_aprov_lancamento": None, "real_aprov_lancamento": None,
        "prev_lancamento": None, "real_lancamento": None,
    }
    assert calcular_cpi_projeto(row) is None


def test_cpi_none_sem_marcos_concluidos():
    row = {
        "valor_total": 500.0, "orcamento": 1000.0,
        "prev_viabilidade": None, "real_viabilidade": None,
        "prev_qualidade": None, "real_qualidade": None,
        "prev_aprov_lancamento": None, "real_aprov_lancamento": None,
        "prev_lancamento": None, "real_lancamento": None,
    }
    assert calcular_cpi_projeto(row) is None


def test_cpi_todos_marcos_concluidos():
    # pct = 1.0, custo=800, orc=1000 → BCWP=1000, CPI=1000/800=1.25
    row = {
        "valor_total": 800.0, "orcamento": 1000.0,
        "prev_viabilidade": "2026-01-01", "real_viabilidade": "2026-01-01",
        "prev_qualidade": "2026-02-01",   "real_qualidade": "2026-02-01",
        "prev_aprov_lancamento": "2026-03-01", "real_aprov_lancamento": "2026-03-01",
        "prev_lancamento": "2026-04-01",  "real_lancamento": "2026-04-01",
    }
    result = calcular_cpi_projeto(row)
    assert result == pytest.approx(1000.0 / 800.0, rel=1e-3)


# ── calcular_forecast_custo inclui cpi ──────────────────────────────────

def test_forecast_custo_inclui_coluna_cpi():
    df_f = _df_proj(prev_viabilidade="2026-01-01", real_viabilidade="2026-01-05")
    df_f["valor_total"] = 400.0
    df_f["orcamento"] = 1000.0
    df_marcos = calcular_marcos(df_f)
    result = calcular_forecast_custo(df_f, df_marcos)
    assert "cpi" in result.columns


def test_forecast_custo_cpi_valor_correto():
    # 45% concluído, custo=400, orc=1000 → CPI = (1000*0.45)/400 = 1.125
    df_f = _df_proj(prev_viabilidade="2026-01-01", real_viabilidade="2026-01-05")
    df_f["valor_total"] = 400.0
    df_f["orcamento"] = 1000.0
    df_marcos = calcular_marcos(df_f)
    result = calcular_forecast_custo(df_f, df_marcos)
    assert result.iloc[0]["cpi"] == pytest.approx(1.125, rel=1e-3)


def test_forecast_custo_cpi_none_sem_pct():
    df_f = _df_proj()  # nenhum marco concluído
    df_f["valor_total"] = 500.0
    df_f["orcamento"] = 1000.0
    df_marcos = calcular_marcos(df_f)
    result = calcular_forecast_custo(df_f, df_marcos)
    assert result.iloc[0]["cpi"] is None or pd.isna(result.iloc[0]["cpi"])
```

- [ ] **Step 2: Rodar os testes e confirmar que TODOS falham**

```
python -m pytest tests/test_dashboard_executivo.py::test_cpi_eficiente_gastou_menos tests/test_dashboard_executivo.py::test_forecast_custo_inclui_coluna_cpi -v
```

Esperado: `ImportError` ou `AssertionError`.

- [ ] **Step 3: Implementar `_cpi` e `calcular_cpi_projeto` em `dashboard_executivo.py`**

Adicionar logo após o bloco `# ─── Forecast de Custo / EAC (Seção 10) ───` e ANTES de `calcular_forecast_custo` (para que `_cpi` e `calcular_cpi_projeto` sejam definidos antes de serem usados):

```python
# ─────────────────────────────────────────────
# CPI — Cost Performance Index
# ─────────────────────────────────────────────

def _cpi(custo: float, orc: float, pct: float) -> float | None:
    """CPI = BCWP / ACWP = (orc × pct) / custo. None se dados insuficientes."""
    if custo <= 0 or orc <= 0 or pct <= 0:
        return None
    return (orc * pct) / custo


def calcular_cpi_projeto(row) -> float | None:
    """
    CPI para uma linha de projeto (dict ou pd.Series).
    Usa MARCOS_CONFIG para somar os pesos dos marcos com data_realizada preenchida.
    Retorna None se custo, orçamento ou % concluído forem zero.
    """
    custo = float(row.get("valor_total", 0) or 0)
    orc   = float(row.get("orcamento", 0) or 0)
    pct   = sum(
        peso
        for _, col_real, _, peso in MARCOS_CONFIG
        if _parse_data(row.get(col_real)) is not None
    )
    return _cpi(custo, orc, pct)
```

- [ ] **Step 4: Atualizar `calcular_forecast_custo` para incluir coluna `cpi`**

Localizar a função `calcular_forecast_custo` em `dashboard_executivo.py`. Substituir o bloco do `linhas.append` para incluir `"cpi"`:

**Antes:**
```python
        linhas.append({
            "nome_projeto":  row.get("nome_projeto", proj),
            "custo_atual":   custo,
            "pct_concluido": pct,
            "eac":           eac,
            "orcamento":     orc,
            "desvio_eac_pct": desvio,
        })
```

**Depois:**
```python
        linhas.append({
            "nome_projeto":   row.get("nome_projeto", proj),
            "custo_atual":    custo,
            "pct_concluido":  pct,
            "eac":            eac,
            "orcamento":      orc,
            "desvio_eac_pct": desvio,
            "cpi":            _cpi(custo, orc, pct),
        })
```

- [ ] **Step 5: Rodar TODOS os testes e confirmar que passam**

```
python -m pytest tests/test_dashboard_executivo.py -v
```

Esperado: todos os testes `PASSED` (incluindo os anteriores + os novos de CPI).

- [ ] **Step 6: Commit**

```bash
git add dashboard_projetos/utils/dashboard_executivo.py dashboard_projetos/tests/test_dashboard_executivo.py
git commit -m "feat: adiciona CPI (calcular_cpi_projeto, _cpi) e inclui cpi em calcular_forecast_custo"
```

---

## Task 3: Página Home Executiva + navegação

**Files:**
- Create: `dashboard_projetos/pages/home.py`
- Modify: `dashboard_projetos/app.py` — adicionar grupo "🏠 Início" com home.py como primeira entrada

**Interfaces:**
- Consumes: `agregar_tudo`, `calcular_risco_portfolio` (de `data_processor`); `calcular_kpis_home`, `calcular_proximos_marcos`, `calcular_marcos_vencidos` (de `dashboard_executivo`); `render_selo_dados`, `formata_brl_curto`, `detectar_excecoes` (de `data_processor`)

- [ ] **Step 1: Criar `dashboard_projetos/pages/home.py`**

```python
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.db import init_db
from utils.data_processor import (
    agregar_tudo,
    calcular_risco_portfolio,
    detectar_excecoes,
    formata_brl_curto,
    render_selo_dados,
)
from utils.dashboard_executivo import (
    calcular_kpis_home,
    calcular_marcos_vencidos,
    calcular_proximos_marcos,
)

init_db()

hoje = datetime.today().date()

st.title("🏠 Home Executiva")
st.caption(f"Visão consolidada do portfólio · {hoje.strftime('%d/%m/%Y')}")

df_dashboard, df_custos_raw, _ = agregar_tudo()

if df_dashboard.empty:
    st.warning(
        "⚠️ Nenhum dado encontrado. "
        "Acesse **Upload de Arquivos** e importe suas planilhas."
    )
    st.stop()

render_selo_dados(df_dashboard)

risco = calcular_risco_portfolio(df_dashboard, df_custos_raw)
kpis  = calcular_kpis_home(df_dashboard, risco)

# ── KPIs ──────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📁 Projetos", kpis["n_ativos"])
c2.metric(
    "🔴 Em risco alto",
    kpis["n_alto_risco"],
    help=(
        "Projetos com projeção de custo acima do orçamento "
        "ou com atraso confirmado em algum marco."
    ),
)
c3.metric(
    "💸 Exposição financeira",
    formata_brl_curto(kpis["exposicao_financeira"])
    if kpis["exposicao_financeira"] > 0
    else "R$ 0",
    help="Soma dos valores projetados de estouro de orçamento nos projetos em risco.",
)
c4.metric(
    "📊 Consumo médio",
    f"{kpis['consumo_medio_pct']:.0f}%",
    help="Percentual médio do orçamento já consumido nos projetos com orçamento cadastrado.",
)
c5.metric(
    "⏰ Atraso médio",
    f"{kpis['atraso_medio_dias']:.0f} d",
    help="Média de dias de atraso no marco mais crítico de cada projeto em risco.",
)

st.divider()

# ── Pontos de atenção ─────────────────────────────────────────────────
st.subheader("⚡ Pontos de Atenção")

exc = detectar_excecoes(df_dashboard)

cartoes = []
if exc["estouro"]:
    cartoes.append(("🚨", len(exc["estouro"]), "acima do orçamento", "#dc2626"))
if exc["atrasados"]:
    cartoes.append(("⏰", len(exc["atrasados"]), "com lançamento atrasado", "#f59e0b"))
if exc["stand_by"]:
    cartoes.append(("⏸️", len(exc["stand_by"]), "em Stand by", "#a78bfa"))
if exc["cancelados"]:
    cartoes.append(("✖️", len(exc["cancelados"]), "cancelados", "#94a3b8"))

if not cartoes:
    st.success("✅ Nenhuma exceção detectada — todos os projetos dentro do previsto.")
else:
    cols_cartoes = st.columns(len(cartoes))
    for col, (icone, n, rotulo, cor) in zip(cols_cartoes, cartoes):
        col.markdown(
            f"""
            <div style="border:1px solid {cor}55;background:{cor}15;border-radius:10px;
                        padding:12px 14px;text-align:center">
                <div style="font-size:22px;font-weight:800;color:{cor}">{icone} {n}</div>
                <div style="font-size:12px;opacity:.8;margin-top:2px">{rotulo}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown("")

# Projetos em alto risco com deep-link para detalhamento
alto_risco = risco[risco["nivel_risco"] == "alto"] if not risco.empty else pd.DataFrame()
if not alto_risco.empty:
    with st.expander(f"🔴 {len(alto_risco)} projeto(s) em alto risco — ver detalhes"):
        for _, r in alto_risco.iterrows():
            pct_s = (
                f"{r['pct_projetado']:.0f}% do orçamento"
                if pd.notna(r["pct_projetado"])
                else "sem orçamento"
            )
            atr_s = (
                f"{r['dias_atraso_max']}d de atraso"
                if r["dias_atraso_max"] > 0
                else "no prazo"
            )
            col_nome, col_btn = st.columns([4, 1])
            col_nome.markdown(f"**{r['nome_projeto']}** — 💰 {pct_s} · ⏰ {atr_s}")
            if col_btn.button(
                "Abrir →",
                key=f"home_ver_{r['projeto']}",
                use_container_width=True,
            ):
                st.session_state["ir_para_projeto"] = r["projeto"]
                st.session_state["ir_para_tab"] = "🔍 Detalhamento"
                st.switch_page(str(_ROOT / "pages" / "3_projetos.py"))

st.divider()

# ── Próximos marcos (7 dias) ──────────────────────────────────────────
st.subheader("📅 Próximos marcos — 7 dias")
df_prox = calcular_proximos_marcos(df_dashboard, dias=7)
if df_prox.empty:
    st.caption("ℹ️ Nenhum marco previsto para os próximos 7 dias.")
else:
    st.dataframe(df_prox, use_container_width=True, hide_index=True)

# ── Marcos vencidos sem conclusão ─────────────────────────────────────
st.subheader("⏰ Marcos vencidos sem conclusão")
df_venc = calcular_marcos_vencidos(df_dashboard)
if df_venc.empty:
    st.success("✅ Nenhum marco com data passada sem conclusão registrada.")
else:
    st.dataframe(df_venc, use_container_width=True, hide_index=True)

st.divider()

# ── Saúde do portfólio ────────────────────────────────────────────────
st.subheader("🎯 Saúde do Portfólio")
s1, s2, s3 = st.columns(3)
s1.metric("🔴 Alto risco",  kpis["n_alto_risco"])
s2.metric("🟡 Risco médio", kpis["n_medio_risco"])
s3.metric("🟢 Baixo risco", kpis["n_baixo_risco"])

st.divider()

# ── Navegação rápida ──────────────────────────────────────────────────
st.subheader("🔗 Navegação Rápida")
n1, n2, n3, n4 = st.columns(4)
if n1.button("🧭 Visão Executiva",     use_container_width=True, type="secondary"):
    st.switch_page(str(_ROOT / "pages" / "4_visao_executiva.py"))
if n2.button("📋 Dashboard Executivo", use_container_width=True, type="secondary"):
    st.switch_page(str(_ROOT / "pages" / "5_dashboard_executivo.py"))
if n3.button("📊 Dashboard Financeiro", use_container_width=True, type="secondary"):
    st.switch_page(str(_ROOT / "pages" / "2_dashboard.py"))
if n4.button("📈 Andamento dos Projetos", use_container_width=True, type="secondary"):
    st.switch_page(str(_ROOT / "pages" / "3_projetos.py"))
```

- [ ] **Step 2: Adicionar a Home ao topo da navegação em `app.py`**

Localizar o bloco `pages = {` em `dashboard_projetos/app.py`. Adicionar o grupo "🏠 Início" como PRIMEIRO grupo:

**Antes:**
```python
pages = {
    "📤 Dados": [
        st.Page(str(ROOT / "pages" / "0_orcamento.py"), title="Orçamentos",        icon="📋"),
        st.Page(str(ROOT / "pages" / "1_upload.py"),    title="Upload de Arquivos", icon="📤"),
    ],
    "🎯 Relatórios Executivos": [
```

**Depois:**
```python
pages = {
    "🏠 Início": [
        st.Page(str(ROOT / "pages" / "home.py"), title="Home Executiva", icon="🏠"),
    ],
    "📤 Dados": [
        st.Page(str(ROOT / "pages" / "0_orcamento.py"), title="Orçamentos",        icon="📋"),
        st.Page(str(ROOT / "pages" / "1_upload.py"),    title="Upload de Arquivos", icon="📤"),
    ],
    "🎯 Relatórios Executivos": [
```

- [ ] **Step 3: Verificar que o app inicia sem erros**

```
python -m streamlit run app.py --server.headless true &
sleep 4
curl -s http://localhost:8501 | head -5
```

Esperado: resposta HTML (não erro Python).

Parar o servidor:
```
pkill -f "streamlit run app.py"
```

- [ ] **Step 4: Commit**

```bash
git add dashboard_projetos/pages/home.py dashboard_projetos/app.py
git commit -m "feat: adiciona Home Executiva como tela inicial do sistema"
```

---

## Task 4: Exibir CPI na tabela EAC do Dashboard Executivo

**Files:**
- Modify: `dashboard_projetos/pages/5_dashboard_executivo.py` — tab "Custos & Recursos", seção "Forecast de Custo (EAC)"

**Interfaces:**
- Consumes: `calcular_forecast_custo` atualizado (Task 2) — coluna `"cpi"` disponível no DataFrame retornado

- [ ] **Step 1: Localizar a seção de exibição do EAC em `5_dashboard_executivo.py`**

Localizar o bloco:
```python
    st.subheader("Forecast de Custo (EAC)")
    df_fc_disp = df_fc.rename(columns={
        "nome_projeto": "Projeto", "custo_atual": "Custo Atual",
        "pct_concluido": "% Concluído", "eac": "EAC",
        "orcamento": "Orçamento", "desvio_eac_pct": "Desvio EAC (%)",
    }).copy()
    df_fc_disp["% Concluído"] = (df_fc_disp["% Concluído"] * 100).round(1)
    st.dataframe(
        df_fc_disp,
        use_container_width=True,
        column_config={
            "Custo Atual":    st.column_config.NumberColumn(format="R$ %.0f"),
            "EAC":            st.column_config.NumberColumn(format="R$ %.0f"),
            "Orçamento":      st.column_config.NumberColumn(format="R$ %.0f"),
            "% Concluído":    st.column_config.ProgressColumn(
                format="%.0f%%", min_value=0, max_value=100
            ),
            "Desvio EAC (%)": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
```

- [ ] **Step 2: Substituir esse bloco para incluir CPI**

```python
    st.subheader("Forecast de Custo (EAC)")
    df_fc_disp = df_fc.rename(columns={
        "nome_projeto":   "Projeto",
        "custo_atual":    "Custo Atual",
        "pct_concluido":  "% Concluído",
        "eac":            "EAC",
        "orcamento":      "Orçamento",
        "desvio_eac_pct": "Desvio EAC (%)",
        "cpi":            "CPI",
    }).copy()
    df_fc_disp["% Concluído"] = (df_fc_disp["% Concluído"] * 100).round(1)
    st.dataframe(
        df_fc_disp,
        use_container_width=True,
        column_config={
            "Custo Atual":    st.column_config.NumberColumn(format="R$ %.0f"),
            "EAC":            st.column_config.NumberColumn(format="R$ %.0f"),
            "Orçamento":      st.column_config.NumberColumn(format="R$ %.0f"),
            "% Concluído":    st.column_config.ProgressColumn(
                format="%.0f%%", min_value=0, max_value=100
            ),
            "Desvio EAC (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "CPI":            st.column_config.NumberColumn(format="%.2f"),
        },
    )
    st.caption(
        "**CPI (Cost Performance Index):** "
        "> 1,00 = eficiente (gasta menos que o planejado) · "
        "= 1,00 = exatamente no orçamento · "
        "< 1,00 = em risco de custo"
    )
```

- [ ] **Step 3: Verificar que o app inicia sem erros de sintaxe**

```
python -c "import ast; ast.parse(open('pages/5_dashboard_executivo.py').read()); print('OK')"
```

Esperado: `OK`.

- [ ] **Step 4: Commit**

```bash
git add dashboard_projetos/pages/5_dashboard_executivo.py
git commit -m "feat: exibe CPI na tabela EAC do Dashboard Executivo"
```

---

## Task 5: Exibir CPI nos KPIs do Detalhamento em Andamento dos Projetos

**Files:**
- Modify: `dashboard_projetos/pages/3_projetos.py` — tab "🔍 Detalhamento", bloco de KPIs do projeto selecionado

**Interfaces:**
- Consumes: `calcular_cpi_projeto(row) -> float | None` (Task 2) — importar de `utils.dashboard_executivo`

- [ ] **Step 1: Adicionar o import de `calcular_cpi_projeto` em `3_projetos.py`**

Localizar o bloco de imports no topo de `3_projetos.py`:
```python
from utils.pdf_report import gerar_relatorio_pdf
from utils import charts
```

Adicionar após esse bloco:
```python
from utils.dashboard_executivo import calcular_cpi_projeto
```

- [ ] **Step 2: Localizar o bloco de KPIs do projeto no Detalhamento**

Localizar em `3_projetos.py`:
```python
    kp4, kp5, kp6 = st.columns(3)
    kp4.metric("⏱️ Horas",        f"{row['horas_total']:.0f} h")
    kp5.metric("📐 Custo/h",      formata_brl(row["custo_por_hora"]))
    kp6.metric("👥 Colaboradores", str(int(row.get("n_colaboradores", 0))))
```

- [ ] **Step 3: Adicionar o KPI de CPI imediatamente após esse bloco**

Adicionar logo após a linha `kp6.metric(...)`:

```python
    cpi_val = calcular_cpi_projeto(row)
    if cpi_val is not None:
        kp7, _, _ = st.columns(3)
        kp7.metric(
            "📊 CPI",
            f"{cpi_val:.2f}",
            delta=f"{cpi_val - 1.0:+.2f} vs referência",
            delta_color="normal",
            help=(
                "Cost Performance Index = (Orçamento × % Marcos Concluídos) / Custo Real.\n\n"
                "**> 1,00** — eficiente: gasta menos que o planejado para o avanço atual\n"
                "**= 1,00** — exatamente no orçamento\n"
                "**< 1,00** — em risco: gasta mais que o planejado para o avanço atual"
            ),
        )
```

- [ ] **Step 4: Verificar que o arquivo não tem erros de sintaxe**

```
python -c "import ast; ast.parse(open('pages/3_projetos.py').read()); print('OK')"
```

Esperado: `OK`.

- [ ] **Step 5: Rodar toda a suíte de testes**

```
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Esperado: todos `PASSED`, zero `FAILED`.

- [ ] **Step 6: Commit**

```bash
git add dashboard_projetos/pages/3_projetos.py
git commit -m "feat: exibe CPI no painel de KPIs do detalhamento de projeto"
```

---

## Self-Review

### Spec coverage

| Requisito | Tarefa |
|---|---|
| Home Executiva como tela inicial | Task 3 (home.py + app.py) |
| KPIs consolidados (total, risco, exposição, consumo, atraso) | Task 1 (`calcular_kpis_home`) + Task 3 (UI) |
| Alertas de exceções na home | Task 3 (usa `detectar_excecoes` existente) |
| Próximos marcos 7 dias | Task 1 (`calcular_proximos_marcos`) + Task 3 (UI) |
| Marcos vencidos sem conclusão | Task 1 (`calcular_marcos_vencidos`) + Task 3 (UI) |
| Deep-link home → detalhamento de projeto | Task 3 (botão "Abrir →" com `st.switch_page`) |
| Navegação rápida na home | Task 3 (4 botões de navegação) |
| CPI calculado com dados existentes | Task 2 (`_cpi`, `calcular_cpi_projeto`) |
| CPI no Dashboard Executivo (tabela EAC) | Task 4 |
| CPI no Andamento dos Projetos (Detalhamento) | Task 5 |

### Placeholder scan

Nenhum placeholder encontrado — todos os steps têm código completo.

### Type consistency

- `_cpi(float, float, float) -> float | None` — definido em Task 2, usado internamente em `calcular_forecast_custo` e externamente via `calcular_cpi_projeto`.
- `calcular_cpi_projeto(row) -> float | None` — definido em Task 2, importado em Task 5 (`3_projetos.py`).
- `calcular_proximos_marcos(df_f, dias=7) -> pd.DataFrame` — definido em Task 1, usado em Task 3 (`home.py`).
- `calcular_marcos_vencidos(df_f) -> pd.DataFrame` — definido em Task 1, usado em Task 3 (`home.py`).
- `calcular_kpis_home(df_dashboard, risco) -> dict` — definido em Task 1, usado em Task 3 (`home.py`).
- `calcular_forecast_custo` retorna DataFrame com coluna `"cpi"` — definido em Task 2, consumido em Task 4.

Nenhuma inconsistência de nomes encontrada.
