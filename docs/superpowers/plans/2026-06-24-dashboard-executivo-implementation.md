# Dashboard Executivo de Projetos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar a página "Dashboard Executivo de Projetos" com 11 seções de análise de prazo, custo, recursos e forecast, numa branch separada para avaliação em localhost antes do deploy.

**Architecture:** Módulo `utils/dashboard_executivo.py` para toda lógica de negócio (funções puras, sem Streamlit), 5 novas funções de gráfico em `utils/charts.py`, página `pages/5_dashboard_executivo.py` que orquestra tudo. Reutiliza `agregar_tudo()` e `render_filtros_sidebar()` existentes.

**Tech Stack:** Python 3.13, Streamlit, Plotly (go), pandas, SQLAlchemy (Postgres/Supabase), pytest

## Global Constraints

- Branch: `feat/dashboard-executivo` — nunca commitar na `main` sem aprovação do usuário
- Nenhuma alteração em `data_processor.py`, `db.py`, `auth.py` ou páginas existentes
- Pesos dos marcos: Viabilidade=0.45, Qualidade=0.40, Aprovação p/ Lançamento=0.05, Lançamento=0.10
- `pct_concluido` armazenado como fração (0.0–1.0); convertido para % apenas na exibição
- `status_visual`: 🟢 atraso_medio_dias≤0 / 🟡 1–30 dias / 🔴 >30 dias
- Todos os gráficos usam `LAYOUT_BASE`, `_LEGEND_H`, `_MARGIN`, `LIMITE_GRAFICO` de `charts.py`
- Restart completo do Streamlit após editar qualquer arquivo em `utils/`

---

## Arquivos

| Ação | Caminho |
|---|---|
| Criar | `dashboard_projetos/utils/dashboard_executivo.py` |
| Criar | `dashboard_projetos/pages/5_dashboard_executivo.py` |
| Criar | `dashboard_projetos/tests/test_dashboard_executivo.py` |
| Modificar | `dashboard_projetos/utils/charts.py` (append 5 funções + 2 dicts de cores) |
| Modificar | `dashboard_projetos/app.py` (adicionar rota) |

---

### Task 0: Criar branch e arquivos vazios

**Files:**
- Create: `dashboard_projetos/utils/dashboard_executivo.py`
- Create: `dashboard_projetos/pages/5_dashboard_executivo.py`
- Create: `dashboard_projetos/tests/test_dashboard_executivo.py`

- [ ] **Step 1: Criar branch**

```bash
git checkout -b feat/dashboard-executivo
```

- [ ] **Step 2: Criar arquivos vazios**

`dashboard_projetos/utils/dashboard_executivo.py`:
```python
"""
dashboard_executivo.py — lógica de negócio para o Dashboard Executivo.
Funções puras: recebem DataFrames, retornam DataFrames/dicts. Sem Streamlit.
"""
```

`dashboard_projetos/pages/5_dashboard_executivo.py`:
```python
# placeholder
```

`dashboard_projetos/tests/test_dashboard_executivo.py`:
```python
# placeholder
```

- [ ] **Step 3: Commit de scaffold**

```bash
git add dashboard_projetos/utils/dashboard_executivo.py \
        dashboard_projetos/pages/5_dashboard_executivo.py \
        dashboard_projetos/tests/test_dashboard_executivo.py
git commit -m "chore: scaffold dashboard executivo files"
```

---

### Task 1: `categorizar_conta()` com TDD

**Files:**
- Modify: `dashboard_projetos/utils/dashboard_executivo.py`
- Modify: `dashboard_projetos/tests/test_dashboard_executivo.py`

**Produces:** `PALAVRAS_CATEGORIA`, `CATEGORIAS_CUSTO`, `categorizar_conta(conta: str) -> str`

- [ ] **Step 1: Escrever testes que falham**

Em `tests/test_dashboard_executivo.py`:
```python
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
```

- [ ] **Step 2: Verificar que os testes falham**

```bash
cd dashboard_projetos && python -m pytest tests/test_dashboard_executivo.py -v 2>&1 | head -30
```
Esperado: `ImportError` ou `FAILED`

- [ ] **Step 3: Implementar em `utils/dashboard_executivo.py`**

```python
"""
dashboard_executivo.py — lógica de negócio para o Dashboard Executivo.
Funções puras: recebem DataFrames, retornam DataFrames/dicts. Sem Streamlit.
"""
from __future__ import annotations

import pandas as pd
from datetime import datetime, date, timedelta

# ─────────────────────────────────────────────
# Categorização de contas
# ─────────────────────────────────────────────

PALAVRAS_CATEGORIA: dict[str, list[str]] = {
    "Mão de obra": ["mão de obra", "mao de obra", "salario", "salário", "pessoal", "folha", "rh"],
    "Terceiros":   ["terceiro", "serviço", "servico", "contratado", "consultoria", "fornecedor"],
    "Materiais":   ["material", "componente", "insumo", "peça", "peca", "estoque"],
    "Viagens":     ["viagem", "hospedagem", "transporte", "diária", "diaria", "deslocamento"],
}

CATEGORIAS_CUSTO: list[str] = list(PALAVRAS_CATEGORIA.keys())


def categorizar_conta(conta) -> str:
    """Retorna categoria de custo pela descrição textual do campo conta."""
    if conta is None or (isinstance(conta, float) and pd.isna(conta)) or str(conta).strip() == "":
        return "Outras"
    conta_lower = str(conta).lower()
    for categoria, palavras in PALAVRAS_CATEGORIA.items():
        if any(p in conta_lower for p in palavras):
            return categoria
    return "Outras"
```

- [ ] **Step 4: Verificar que os testes passam**

```bash
python -m pytest tests/test_dashboard_executivo.py -v 2>&1 | head -30
```
Esperado: todos `PASSED`

- [ ] **Step 5: Commit**

```bash
git add dashboard_projetos/utils/dashboard_executivo.py \
        dashboard_projetos/tests/test_dashboard_executivo.py
git commit -m "feat: categorizar_conta com TDD"
```

---

### Task 2: `calcular_marcos()` com TDD

**Files:**
- Modify: `dashboard_projetos/utils/dashboard_executivo.py`
- Modify: `dashboard_projetos/tests/test_dashboard_executivo.py`

**Produces:** `MARCOS_CONFIG`, `_parse_data()`, `calcular_marcos(df) -> pd.DataFrame`

Colunas de saída: `projeto, nome_projeto, marco, peso, data_prevista, data_realizada, desvio_dias, status_marco, concluido`

- [ ] **Step 1: Adicionar testes**

Append em `tests/test_dashboard_executivo.py`:
```python
from utils.dashboard_executivo import calcular_marcos, MARCOS_CONFIG

def _df_proj(**overrides):
    """DataFrame de 1 projeto com todos os marcos None por padrão."""
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
    result = calcular_marcos(_df_proj())
    assert len(result) == 4

def test_calcular_marcos_pesos_somam_1():
    pesos = [cfg[3] for cfg in MARCOS_CONFIG]
    assert abs(sum(pesos) - 1.0) < 1e-9

def test_calcular_marcos_viabilidade_peso():
    result = calcular_marcos(_df_proj())
    peso = result[result["marco"] == "Viabilidade"]["peso"].iloc[0]
    assert peso == pytest.approx(0.45)

def test_calcular_marcos_qualidade_peso():
    result = calcular_marcos(_df_proj())
    peso = result[result["marco"] == "Qualidade"]["peso"].iloc[0]
    assert peso == pytest.approx(0.40)

def test_calcular_marcos_aprov_peso():
    result = calcular_marcos(_df_proj())
    peso = result[result["marco"] == "Aprovação p/ Lançamento"]["peso"].iloc[0]
    assert peso == pytest.approx(0.05)

def test_calcular_marcos_lancamento_peso():
    result = calcular_marcos(_df_proj())
    peso = result[result["marco"] == "Lançamento"]["peso"].iloc[0]
    assert peso == pytest.approx(0.10)

def test_calcular_marcos_sem_datas_pendente():
    result = calcular_marcos(_df_proj())
    assert (result["status_marco"] == "Pendente").all()
    assert not result["concluido"].any()

def test_calcular_marcos_concluido_no_prazo():
    result = calcular_marcos(_df_proj(
        prev_viabilidade="2026-01-15",
        real_viabilidade="2026-01-10",
    ))
    row = result[result["marco"] == "Viabilidade"].iloc[0]
    assert row["concluido"] is True
    assert row["status_marco"] == "Concluído"
    assert row["desvio_dias"] == -5

def test_calcular_marcos_concluido_atrasado():
    result = calcular_marcos(_df_proj(
        prev_viabilidade="2026-01-01",
        real_viabilidade="2026-01-11",
    ))
    row = result[result["marco"] == "Viabilidade"].iloc[0]
    assert row["status_marco"] == "Atrasado"
    assert row["desvio_dias"] == 10

def test_calcular_marcos_pct_parcial():
    # Viabilidade (0.45) + Qualidade (0.40) = 0.85
    result = calcular_marcos(_df_proj(
        prev_viabilidade="2026-01-01", real_viabilidade="2026-01-05",
        prev_qualidade="2026-03-01",   real_qualidade="2026-03-01",
    ))
    pct = result[result["concluido"]]["peso"].sum()
    assert pct == pytest.approx(0.85)

def test_calcular_marcos_todos_concluidos():
    result = calcular_marcos(_df_proj(
        prev_viabilidade="2026-01-01", real_viabilidade="2026-01-05",
        prev_qualidade="2026-03-01",   real_qualidade="2026-03-01",
        prev_aprov_lancamento="2026-05-01", real_aprov_lancamento="2026-05-02",
        prev_lancamento="2026-06-01",  real_lancamento="2026-06-01",
    ))
    pct = result[result["concluido"]]["peso"].sum()
    assert pct == pytest.approx(1.0)
```

- [ ] **Step 2: Verificar que falham**

```bash
python -m pytest tests/test_dashboard_executivo.py -k "marcos" -v 2>&1 | head -20
```
Esperado: `ImportError` pois `calcular_marcos` não existe ainda.

- [ ] **Step 3: Implementar — append em `utils/dashboard_executivo.py`**

```python
# ─────────────────────────────────────────────
# Marcos
# ─────────────────────────────────────────────

MARCOS_CONFIG: list[tuple[str, str, str, float]] = [
    ("prev_viabilidade",      "real_viabilidade",      "Viabilidade",            0.45),
    ("prev_qualidade",        "real_qualidade",        "Qualidade",               0.40),
    ("prev_aprov_lancamento", "real_aprov_lancamento", "Aprovação p/ Lançamento", 0.05),
    ("prev_lancamento",       "real_lancamento",       "Lançamento",              0.10),
]


def _parse_data(val) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if s in ("", "0", "None", "nan"):
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def calcular_marcos(df: pd.DataFrame) -> pd.DataFrame:
    hoje = datetime.today().date()
    linhas: list[dict] = []
    for _, row in df.iterrows():
        for col_prev, col_real, label, peso in MARCOS_CONFIG:
            prev_d = _parse_data(row.get(col_prev))
            real_d = _parse_data(row.get(col_real))
            concluido = real_d is not None
            if concluido:
                desvio = (real_d - prev_d).days if prev_d else 0
                status = "Atrasado" if desvio > 0 else "Concluído"
            elif prev_d is not None:
                desvio = (hoje - prev_d).days
                status = "Atrasado" if desvio > 0 else "Pendente"
            else:
                desvio, status = 0, "Pendente"
            linhas.append({
                "projeto":        row.get("projeto"),
                "nome_projeto":   row.get("nome_projeto", row.get("projeto")),
                "marco":          label,
                "peso":           peso,
                "data_prevista":  prev_d,
                "data_realizada": real_d,
                "desvio_dias":    desvio,
                "status_marco":   status,
                "concluido":      concluido,
            })
    return pd.DataFrame(linhas)
```

- [ ] **Step 4: Verificar que passam**

```bash
python -m pytest tests/test_dashboard_executivo.py -v 2>&1 | tail -20
```
Esperado: todos `PASSED`

- [ ] **Step 5: Commit**

```bash
git add dashboard_projetos/utils/dashboard_executivo.py \
        dashboard_projetos/tests/test_dashboard_executivo.py
git commit -m "feat: calcular_marcos com pesos configuráveis e TDD"
```

---

### Task 3: `calcular_burn_rate()` com TDD

**Files:**
- Modify: `dashboard_projetos/utils/dashboard_executivo.py`
- Modify: `dashboard_projetos/tests/test_dashboard_executivo.py`

**Produces:** `calcular_burn_rate(df_custos_f) -> pd.DataFrame`

Colunas de saída: `projeto, mes_ref, custo_mensal, custo_acumulado, burn_rate`

- [ ] **Step 1: Adicionar testes**

```python
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
```

- [ ] **Step 2: Verificar que falham**

```bash
python -m pytest tests/test_dashboard_executivo.py -k "burn_rate" -v 2>&1 | head -10
```

- [ ] **Step 3: Implementar — append em `utils/dashboard_executivo.py`**

```python
# ─────────────────────────────────────────────
# Burn Rate (Seção 8)
# ─────────────────────────────────────────────

def calcular_burn_rate(df_custos_f: pd.DataFrame) -> pd.DataFrame:
    if df_custos_f.empty or "mes_ref" not in df_custos_f.columns:
        return pd.DataFrame(columns=["projeto", "mes_ref", "custo_mensal", "custo_acumulado", "burn_rate"])
    df = (
        df_custos_f.groupby(["centro_de_custo", "mes_ref"])["realizado"]
        .sum().reset_index()
        .rename(columns={"centro_de_custo": "projeto", "realizado": "custo_mensal"})
        .sort_values(["projeto", "mes_ref"])
    )
    df["custo_acumulado"] = df.groupby("projeto")["custo_mensal"].cumsum()
    df["_n"] = df.groupby("projeto").cumcount() + 1
    df["burn_rate"] = df["custo_acumulado"] / df["_n"]
    return df.drop(columns=["_n"])
```

- [ ] **Step 4: Verificar que passam**

```bash
python -m pytest tests/test_dashboard_executivo.py -k "burn_rate" -v
```

- [ ] **Step 5: Commit**

```bash
git add dashboard_projetos/utils/dashboard_executivo.py \
        dashboard_projetos/tests/test_dashboard_executivo.py
git commit -m "feat: calcular_burn_rate com TDD"
```

---

### Task 4: `calcular_forecast_prazo()`, `calcular_forecast_custo()`, `calcular_matriz_prazo_custo()` com TDD

**Files:**
- Modify: `dashboard_projetos/utils/dashboard_executivo.py`
- Modify: `dashboard_projetos/tests/test_dashboard_executivo.py`

**Consumes:** `calcular_marcos()`, `_parse_data()`

**Produces:**
- `calcular_forecast_prazo(df_f, df_marcos) -> pd.DataFrame` — colunas: `nome_projeto, data_planejada, atraso_medio_dias, forecast, desvio_total`
- `calcular_forecast_custo(df_f, df_marcos) -> pd.DataFrame` — colunas: `nome_projeto, custo_atual, pct_concluido, eac, orcamento, desvio_eac_pct`
- `calcular_matriz_prazo_custo(df_fp, df_fc) -> pd.DataFrame` — colunas: `nome_projeto, desvio_prazo_dias, desvio_eac_pct, quadrante`

- [ ] **Step 1: Adicionar testes**

```python
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
```

- [ ] **Step 2: Verificar que falham**

```bash
python -m pytest tests/test_dashboard_executivo.py -k "forecast or matriz" -v 2>&1 | head -15
```

- [ ] **Step 3: Implementar — append em `utils/dashboard_executivo.py`**

```python
# ─────────────────────────────────────────────
# Forecast de Prazo (Seção 9)
# ─────────────────────────────────────────────

def calcular_forecast_prazo(df_f: pd.DataFrame, df_marcos: pd.DataFrame) -> pd.DataFrame:
    atraso_medio = (
        df_marcos[df_marcos["concluido"] & (df_marcos["desvio_dias"] > 0)]
        .groupby("projeto")["desvio_dias"].mean().round()
    )
    linhas: list[dict] = []
    for _, row in df_f.iterrows():
        proj = row["projeto"]
        prev_lanc = _parse_data(row.get("prev_lancamento"))
        atraso_d = int(atraso_medio.get(proj, 0) or 0)
        forecast = (prev_lanc + timedelta(days=atraso_d)) if prev_lanc else None
        linhas.append({
            "nome_projeto":      row.get("nome_projeto", proj),
            "data_planejada":    prev_lanc,
            "atraso_medio_dias": atraso_d,
            "forecast":          forecast,
            "desvio_total":      atraso_d,
        })
    return pd.DataFrame(linhas)


# ─────────────────────────────────────────────
# Forecast de Custo / EAC (Seção 10)
# ─────────────────────────────────────────────

def calcular_forecast_custo(df_f: pd.DataFrame, df_marcos: pd.DataFrame) -> pd.DataFrame:
    pct_por_proj = (
        df_marcos[df_marcos["concluido"]].groupby("projeto")["peso"].sum()
    )
    linhas: list[dict] = []
    for _, row in df_f.iterrows():
        proj  = row["projeto"]
        custo = float(row.get("valor_total", 0) or 0)
        orc   = float(row.get("orcamento", 0) or 0)
        pct   = float(pct_por_proj.get(proj, 0) or 0)
        eac   = (custo / pct) if pct > 0 else None
        desvio = ((eac - orc) / orc * 100) if (eac is not None and orc > 0) else None
        linhas.append({
            "nome_projeto":  row.get("nome_projeto", proj),
            "custo_atual":   custo,
            "pct_concluido": pct,
            "eac":           eac,
            "orcamento":     orc,
            "desvio_eac_pct": desvio,
        })
    return pd.DataFrame(linhas)


# ─────────────────────────────────────────────
# Matriz Executiva Prazo × Custo (Seção 11)
# ─────────────────────────────────────────────

def calcular_matriz_prazo_custo(
    df_forecast_prazo: pd.DataFrame,
    df_forecast_custo: pd.DataFrame,
) -> pd.DataFrame:
    df = (
        df_forecast_prazo[["nome_projeto", "desvio_total"]]
        .rename(columns={"desvio_total": "desvio_prazo_dias"})
        .merge(df_forecast_custo[["nome_projeto", "desvio_eac_pct"]], on="nome_projeto", how="inner")
        .dropna(subset=["desvio_eac_pct"])
    )
    if df.empty:
        return df.assign(quadrante=pd.Series(dtype=str))

    def _quad(row) -> str:
        x, y = row["desvio_prazo_dias"], row["desvio_eac_pct"]
        if x <= 0 and y <= 0: return "Controlado"
        if x > 0  and y <= 0: return "Risco de Prazo"
        if x <= 0 and y > 0:  return "Risco de Custo"
        return "Crítico"

    df["quadrante"] = df.apply(_quad, axis=1)
    return df
```

- [ ] **Step 4: Verificar que passam**

```bash
python -m pytest tests/test_dashboard_executivo.py -k "forecast or matriz" -v
```

- [ ] **Step 5: Commit**

```bash
git add dashboard_projetos/utils/dashboard_executivo.py \
        dashboard_projetos/tests/test_dashboard_executivo.py
git commit -m "feat: forecast de prazo, custo (EAC) e matriz executiva com TDD"
```

---

### Task 5: Funções auxiliares de agregação com TDD

**Files:**
- Modify: `dashboard_projetos/utils/dashboard_executivo.py`
- Modify: `dashboard_projetos/tests/test_dashboard_executivo.py`

**Produces:**
- `calcular_resumo_executivo(df_f, df_custos_f, df_horas_f, df_marcos) -> dict`
- `calcular_status_projetos(df_f, df_marcos, df_custos_f, df_horas_f) -> pd.DataFrame`
- `calcular_custos_por_categoria(df_custos_f) -> pd.DataFrame`
- `calcular_recursos(df_f, df_horas_f) -> pd.DataFrame`

- [ ] **Step 1: Adicionar testes**

```python
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
```

- [ ] **Step 2: Verificar que falham**

```bash
python -m pytest tests/test_dashboard_executivo.py -k "resumo or status_proj or categoria or recursos" -v 2>&1 | head -15
```

- [ ] **Step 3: Implementar — append em `utils/dashboard_executivo.py`**

```python
# ─────────────────────────────────────────────
# Resumo Executivo (Seção 1)
# ─────────────────────────────────────────────

_STATUS_TERMINAIS = {"Cancelado", "Lançado"}


def calcular_resumo_executivo(
    df_f: pd.DataFrame,
    df_custos_f: pd.DataFrame,
    df_horas_f: pd.DataFrame,
    df_marcos: pd.DataFrame,
) -> dict:
    if "status_projeto" in df_f.columns:
        projetos_ativos = int(
            df_f["status_projeto"].apply(lambda s: str(s).strip() not in _STATUS_TERMINAIS).sum()
        )
    else:
        projetos_ativos = len(df_f)

    atrasados_set = set(df_marcos[df_marcos["status_marco"] == "Atrasado"]["projeto"].unique())
    projetos_com_atraso = len(atrasados_set & set(df_f["projeto"].unique()))

    horas  = float(df_horas_f["hs_nor"].sum())  if (not df_horas_f.empty  and "hs_nor"    in df_horas_f.columns)  else 0.0
    custos = float(df_custos_f["realizado"].sum()) if (not df_custos_f.empty and "realizado" in df_custos_f.columns) else 0.0

    pct_s = (
        df_marcos[df_marcos["concluido"]].groupby("projeto")["peso"].sum()
        .reindex(df_f["projeto"].unique()).fillna(0.0)
    )
    pct_medio = float(pct_s.mean()) if not pct_s.empty else 0.0

    atrasos = df_marcos[df_marcos["concluido"] & (df_marcos["desvio_dias"] > 0)]["desvio_dias"]
    prazo_medio = float(atrasos.mean()) if not atrasos.empty else 0.0

    return {
        "projetos_ativos":     projetos_ativos,
        "projetos_com_atraso": projetos_com_atraso,
        "horas_consumidas":    horas,
        "custos_acumulados":   custos,
        "pct_medio_conclusao": pct_medio,
        "prazo_medio_atraso":  prazo_medio,
    }


# ─────────────────────────────────────────────
# Status Geral dos Projetos (Seção 2)
# ─────────────────────────────────────────────

def calcular_status_projetos(
    df_f: pd.DataFrame,
    df_marcos: pd.DataFrame,
    df_custos_f: pd.DataFrame,
    df_horas_f: pd.DataFrame,
) -> pd.DataFrame:
    pct = (
        df_marcos[df_marcos["concluido"]].groupby("projeto")["peso"].sum()
        .reset_index().rename(columns={"peso": "pct_concluido"})
    )
    marcos_ok = (
        df_marcos[df_marcos["concluido"]].groupby("projeto").size()
        .reset_index(name="marcos_concluidos")
    )
    atraso = (
        df_marcos[df_marcos["status_marco"] == "Atrasado"]
        .groupby("projeto")["desvio_dias"].mean()
        .reset_index().rename(columns={"desvio_dias": "atraso_medio_dias"})
    )
    horas_p = pd.DataFrame(columns=["projeto", "horas_total"])
    if not df_horas_f.empty and "c_custo" in df_horas_f.columns:
        horas_p = (
            df_horas_f.groupby("c_custo")["hs_nor"].sum()
            .reset_index().rename(columns={"c_custo": "projeto", "hs_nor": "horas_total"})
        )
    custos_p = pd.DataFrame(columns=["projeto", "custo_total"])
    if not df_custos_f.empty and "centro_de_custo" in df_custos_f.columns:
        custos_p = (
            df_custos_f.groupby("centro_de_custo")["realizado"].sum()
            .reset_index().rename(columns={"centro_de_custo": "projeto", "realizado": "custo_total"})
        )
    cols = ["projeto", "nome_projeto"]
    if "status_projeto" in df_f.columns:
        cols.append("status_projeto")
    result = (
        df_f[cols].copy()
        .merge(pct,      on="projeto", how="left")
        .merge(marcos_ok, on="projeto", how="left")
        .merge(atraso,   on="projeto", how="left")
        .merge(horas_p,  on="projeto", how="left")
        .merge(custos_p, on="projeto", how="left")
    )
    result["pct_concluido"]     = result["pct_concluido"].fillna(0.0)
    result["marcos_concluidos"] = result["marcos_concluidos"].fillna(0).astype(int)
    result["marcos_totais"]     = 4
    result["atraso_medio_dias"] = result["atraso_medio_dias"].fillna(0.0)
    result["horas_total"]       = result.get("horas_total", pd.Series(0.0, index=result.index)).fillna(0.0)
    result["custo_total"]       = result.get("custo_total", pd.Series(0.0, index=result.index)).fillna(0.0)
    result["status_visual"] = result["atraso_medio_dias"].apply(
        lambda a: "🟢" if a <= 0 else ("🟡" if a <= 30 else "🔴")
    )
    return result


# ─────────────────────────────────────────────
# Custos por Categoria (Seções 5, 6)
# ─────────────────────────────────────────────

def calcular_custos_por_categoria(df_custos_f: pd.DataFrame) -> pd.DataFrame:
    if df_custos_f.empty or "centro_de_custo" not in df_custos_f.columns:
        return pd.DataFrame(columns=["projeto", "categoria_custo", "total_custo"])
    df = df_custos_f.copy()
    if "categoria_custo" not in df.columns:
        df["categoria_custo"] = df.get("conta", pd.Series("", index=df.index)).apply(categorizar_conta)
    return (
        df.groupby(["centro_de_custo", "categoria_custo"])["realizado"].sum()
        .reset_index().rename(columns={"centro_de_custo": "projeto", "realizado": "total_custo"})
    )


# ─────────────────────────────────────────────
# Consumo de Recursos (Seção 7)
# ─────────────────────────────────────────────

def calcular_recursos(df_f: pd.DataFrame, df_horas_f: pd.DataFrame) -> pd.DataFrame:
    if df_horas_f.empty or "c_custo" not in df_horas_f.columns:
        return pd.DataFrame(columns=["nome_projeto", "horas_total", "n_colaboradores", "horas_por_colaborador"])
    agg = (
        df_horas_f.groupby("c_custo")
        .agg(horas_total=("hs_nor", "sum"), n_colaboradores=("nome", "nunique"))
        .reset_index().rename(columns={"c_custo": "projeto"})
    )
    agg["horas_por_colaborador"] = agg.apply(
        lambda r: r["horas_total"] / r["n_colaboradores"] if r["n_colaboradores"] > 0 else 0.0, axis=1
    )
    nomes = df_f[["projeto", "nome_projeto"]].drop_duplicates("projeto")
    return agg.merge(nomes, on="projeto", how="left")
```

- [ ] **Step 4: Verificar que todos os testes passam**

```bash
python -m pytest tests/test_dashboard_executivo.py -v 2>&1 | tail -25
```
Esperado: todos `PASSED`

- [ ] **Step 5: Commit**

```bash
git add dashboard_projetos/utils/dashboard_executivo.py \
        dashboard_projetos/tests/test_dashboard_executivo.py
git commit -m "feat: resumo executivo, status projetos, custos por categoria e recursos com TDD"
```

---

### Task 6: Funções de gráfico em `charts.py`

**Files:**
- Modify: `dashboard_projetos/utils/charts.py`

**Consumes:** `LAYOUT_BASE`, `_LEGEND_H`, `_MARGIN`, `LIMITE_GRAFICO`, `CORES` (já existem)

**Produces:** `CORES_CATEGORIA`, `_COR_QUADRANTE`, `grafico_evolucao_fisica`, `grafico_custos_empilhados`, `grafico_distribuicao_custos`, `grafico_burn_rate_temporal`, `grafico_matriz_executiva`

- [ ] **Step 1: Fazer append em `utils/charts.py`**

Adicionar ao final do arquivo:

```python
# ─────────────────────────────────────────────
# Dashboard Executivo — gráficos
# ─────────────────────────────────────────────

CORES_CATEGORIA: dict[str, str] = {
    "Mão de obra": "#4C78A8",
    "Terceiros":   "#F58518",
    "Materiais":   "#54A24B",
    "Viagens":     "#B279A2",
    "Outras":      "#9D755D",
}

_COR_QUADRANTE: dict[str, str] = {
    "Controlado":     "#22c55e",
    "Risco de Prazo": "#f59e0b",
    "Risco de Custo": "#f97316",
    "Crítico":        "#ef4444",
}


def grafico_evolucao_fisica(df_status: pd.DataFrame) -> go.Figure:
    """Barras horizontais de % concluído por projeto. df_status: nome_projeto, pct_concluido (0-1)."""
    df_plot = df_status.sort_values("pct_concluido", ascending=True).tail(LIMITE_GRAFICO)
    fig = go.Figure(go.Bar(
        y=df_plot["nome_projeto"],
        x=(df_plot["pct_concluido"] * 100).round(1),
        orientation="h",
        marker_color="#4C78A8",
        text=[f"{v*100:.0f}%" for v in df_plot["pct_concluido"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Concluído: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Evolução Física dos Projetos</b>",
        margin=_MARGIN,
        xaxis=dict(range=[0, 115], ticksuffix="%", gridcolor="rgba(128,128,128,.15)"),
    )
    return fig


def grafico_custos_empilhados(df_cat: pd.DataFrame) -> go.Figure:
    """Barras empilhadas custo por projeto e categoria. df_cat: nome_projeto, categoria_custo, total_custo."""
    eixo = "nome_projeto" if "nome_projeto" in df_cat.columns else "projeto"
    nomes = df_cat[eixo].unique()[:LIMITE_GRAFICO]
    fig = go.Figure()
    for cat in ["Mão de obra", "Terceiros", "Materiais", "Viagens", "Outras"]:
        df_c = df_cat[df_cat["categoria_custo"] == cat]
        valores = [float(df_c[df_c[eixo] == p]["total_custo"].sum()) for p in nomes]
        if any(v > 0 for v in valores):
            fig.add_trace(go.Bar(
                name=cat, x=list(nomes), y=valores,
                marker_color=CORES_CATEGORIA.get(cat, "#94a3b8"),
                hovertemplate=f"<b>%{{x}}</b><br>{cat}: R$ %{{y:,.0f}}<extra></extra>",
            ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Custos por Projeto e Categoria</b>",
        barmode="stack", legend=_LEGEND_H, margin=_MARGIN,
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(128,128,128,.15)"),
        xaxis=dict(tickangle=-30),
    )
    return fig


def grafico_distribuicao_custos(df_cat: pd.DataFrame) -> go.Figure:
    """Donut de custos por categoria. df_cat: categoria_custo, total_custo."""
    total = df_cat.groupby("categoria_custo")["total_custo"].sum().reset_index()
    fig = go.Figure(go.Pie(
        labels=total["categoria_custo"],
        values=total["total_custo"],
        hole=0.45,
        marker_colors=[CORES_CATEGORIA.get(c, "#94a3b8") for c in total["categoria_custo"]],
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.0f} · %{percent}<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Distribuição de Custos por Categoria</b>",
        margin=_MARGIN, legend=_LEGEND_H,
    )
    return fig


def grafico_burn_rate_temporal(df_br: pd.DataFrame) -> go.Figure:
    """Linha de custo acumulado mensal (top 10 projetos). df_br: projeto, mes_ref, custo_acumulado."""
    top_projs = (
        df_br.groupby("projeto")["custo_acumulado"].max()
        .nlargest(10).index.tolist()
    )
    fig = go.Figure()
    for i, proj in enumerate(top_projs):
        df_p = df_br[df_br["projeto"] == proj].sort_values("mes_ref")
        fig.add_trace(go.Scatter(
            x=df_p["mes_ref"], y=df_p["custo_acumulado"],
            mode="lines+markers", name=proj[:20],
            line=dict(color=CORES[i % len(CORES)]),
            hovertemplate=f"<b>{proj[:20]}</b><br>%{{x}}<br>Acumulado: R$ %{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Burn Rate — Custo Acumulado por Projeto</b>",
        legend=_LEGEND_H, margin=_MARGIN,
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(128,128,128,.15)"),
        xaxis=dict(gridcolor="rgba(128,128,128,.15)"),
    )
    return fig


def grafico_matriz_executiva(df_matriz: pd.DataFrame) -> go.Figure:
    """Scatter de quadrantes. df_matriz: nome_projeto, desvio_prazo_dias, desvio_eac_pct, quadrante."""
    fig = go.Figure()
    for quadrante, grp in df_matriz.groupby("quadrante"):
        fig.add_trace(go.Scatter(
            x=grp["desvio_prazo_dias"], y=grp["desvio_eac_pct"],
            mode="markers+text", name=quadrante,
            marker=dict(size=14, color=_COR_QUADRANTE.get(quadrante, "#94a3b8"),
                        opacity=0.85, line=dict(width=1, color="rgba(255,255,255,0.2)")),
            text=grp["nome_projeto"].apply(lambda n: (str(n)[:12] + "…") if len(str(n)) > 12 else str(n)),
            textposition="top center",
            textfont=dict(size=9, color="rgba(255,255,255,0.85)"),
            hovertemplate="<b>%{text}</b><br>Desvio prazo: %{x} dias<br>Desvio custo: %{y:.1f}%<extra></extra>",
        ))
    fig.add_vline(x=0, line_dash="dash", line_color="rgba(148,163,184,.4)")
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(148,163,184,.4)")
    for texto, xr, yr, xa, ya in [
        ("🟢 Controlado",  0.02, 0.02, "left",  "bottom"),
        ("🟡 Risco Prazo", 0.98, 0.02, "right", "bottom"),
        ("🟠 Risco Custo", 0.02, 0.98, "left",  "top"),
        ("🔴 Crítico",     0.98, 0.98, "right", "top"),
    ]:
        fig.add_annotation(xref="paper", yref="paper", x=xr, y=yr, text=texto,
                           showarrow=False, font=dict(size=10, color="rgba(148,163,184,.55)"),
                           xanchor=xa, yanchor=ya)
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Matriz Executiva — Prazo × Custo</b>",
        legend=_LEGEND_H, margin=_MARGIN,
        xaxis_title="Desvio de Prazo (dias)",
        yaxis_title="Desvio de Custo EAC (%)",
        xaxis=dict(zeroline=False, gridcolor="rgba(128,128,128,.15)"),
        yaxis=dict(zeroline=False, gridcolor="rgba(128,128,128,.15)"),
        hovermode="closest",
    )
    return fig
```

- [ ] **Step 2: Verificar importação**

```bash
python -c "from utils.charts import grafico_evolucao_fisica, grafico_custos_empilhados, grafico_distribuicao_custos, grafico_burn_rate_temporal, grafico_matriz_executiva; print('OK')"
```
Esperado: `OK`

- [ ] **Step 3: Commit**

```bash
git add dashboard_projetos/utils/charts.py
git commit -m "feat: 5 novos gráficos para dashboard executivo em charts.py"
```

---

### Task 7: Página `5_dashboard_executivo.py`

**Files:**
- Modify: `dashboard_projetos/pages/5_dashboard_executivo.py`

**Consumes:** todos os módulos implementados nas tasks anteriores

- [ ] **Step 1: Escrever a página completa**

```python
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st
from utils.db import init_db
from utils.data_processor import (
    agregar_tudo, render_filtros_sidebar, formata_brl_curto,
)
from utils.dashboard_executivo import (
    CATEGORIAS_CUSTO, categorizar_conta,
    calcular_marcos, calcular_resumo_executivo, calcular_status_projetos,
    calcular_custos_por_categoria, calcular_recursos, calcular_burn_rate,
    calcular_forecast_prazo, calcular_forecast_custo, calcular_matriz_prazo_custo,
)
from utils import charts

init_db()

st.title("📋 Dashboard Executivo de Projetos")
st.caption("Visão consolidada de prazo, custo, recursos e previsões.")

df_dashboard, df_custos_raw, df_horas_raw = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

df_f = render_filtros_sidebar(df_dashboard, df_custos_raw)

with st.sidebar:
    st.divider()
    st.subheader("🔍 Filtros desta página")
    cat_sel = st.multiselect(
        "Categoria de Custo:",
        options=CATEGORIAS_CUSTO + ["Outras"],
        default=[],
        key="exec_filtro_categoria_custo",
    )
    colabs = (
        sorted(df_horas_raw[df_horas_raw["c_custo"].isin(df_f["projeto"])]["nome"].dropna().unique())
        if not df_horas_raw.empty else []
    )
    colab_sel = st.multiselect("Colaborador:", options=colabs, default=[], key="exec_filtro_colaborador")

if df_f.empty:
    st.info("Nenhum projeto encontrado para os filtros selecionados.")
    st.stop()

projetos_f = df_f["projeto"].unique()

df_custos_f = (
    df_custos_raw[df_custos_raw["centro_de_custo"].isin(projetos_f)].copy()
    if not df_custos_raw.empty else pd.DataFrame()
)
df_horas_f = (
    df_horas_raw[df_horas_raw["c_custo"].isin(projetos_f)].copy()
    if not df_horas_raw.empty else pd.DataFrame()
)

if colab_sel and not df_horas_f.empty:
    df_horas_f = df_horas_f[df_horas_f["nome"].isin(colab_sel)]

if not df_custos_f.empty and "conta" in df_custos_f.columns:
    df_custos_f["categoria_custo"] = df_custos_f["conta"].apply(categorizar_conta)
    if cat_sel:
        df_custos_f = df_custos_f[df_custos_f["categoria_custo"].isin(cat_sel)]

df_marcos = calcular_marcos(df_f)

# ── 1. Resumo Executivo ───────────────────────────────────────────────────────
st.subheader("📊 1. Resumo Executivo")
resumo = calcular_resumo_executivo(df_f, df_custos_f, df_horas_f, df_marcos)
c1, c2, c3 = st.columns(3)
c4, c5, c6 = st.columns(3)
c1.metric("📁 Projetos Ativos",       resumo["projetos_ativos"])
c2.metric("⚠️ Com Atraso",           resumo["projetos_com_atraso"])
c3.metric("⏱️ Horas Consumidas",     f"{resumo['horas_consumidas']:,.0f} h")
c4.metric("💰 Custos Acumulados",     formata_brl_curto(resumo["custos_acumulados"]))
c5.metric("✅ % Médio Conclusão",     f"{resumo['pct_medio_conclusao']*100:.1f}%")
c6.metric("📅 Atraso Médio",          f"{resumo['prazo_medio_atraso']:.0f} dias")
st.divider()

# ── 2. Status Geral ───────────────────────────────────────────────────────────
st.subheader("📋 2. Status Geral dos Projetos")
df_status = calcular_status_projetos(df_f, df_marcos, df_custos_f, df_horas_f)
busca = st.text_input("🔎 Buscar projeto:", key="exec_busca_projeto")
if busca:
    df_status = df_status[df_status["nome_projeto"].str.contains(busca, case=False, na=False)]
colunas_exib = {
    "status_visual": "", "nome_projeto": "Projeto",
    "pct_concluido": "% Concluído", "marcos_concluidos": "Marcos Conc.",
    "marcos_totais": "Marcos Tot.", "atraso_medio_dias": "Atraso Médio (d)",
    "horas_total": "Horas", "custo_total": "Custo",
}
if "status_projeto" in df_status.columns:
    colunas_exib["status_projeto"] = "Status"
st.dataframe(
    df_status[[c for c in colunas_exib if c in df_status.columns]].rename(columns=colunas_exib),
    use_container_width=True,
    column_config={
        "% Concluído": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
        "Custo": st.column_config.NumberColumn(format="R$ %.0f"),
        "Horas": st.column_config.NumberColumn(format="%.0f h"),
    },
)
st.divider()

# ── 3. Evolução Física ────────────────────────────────────────────────────────
st.subheader("📈 3. Evolução Física dos Projetos")
fig_evo = charts.grafico_evolucao_fisica(df_status)
st.plotly_chart(fig_evo, use_container_width=True)
with st.expander("🔍 Ver marcos de um projeto"):
    proj_nome = st.selectbox("Projeto:", df_f["nome_projeto"].unique(), key="exec_proj_drill")
    if proj_nome:
        proj_id = df_f[df_f["nome_projeto"] == proj_nome]["projeto"].iloc[0]
        st.dataframe(
            df_marcos[df_marcos["projeto"] == proj_id][
                ["marco", "data_prevista", "data_realizada", "desvio_dias", "status_marco"]
            ].rename(columns={
                "marco": "Marco", "data_prevista": "Previsto",
                "data_realizada": "Realizado", "desvio_dias": "Desvio (d)", "status_marco": "Status",
            }),
            use_container_width=True,
        )
st.divider()

# ── 4. Análise de Marcos ──────────────────────────────────────────────────────
st.subheader("🗓️ 4. Análise de Marcos")
total_m    = len(df_marcos)
atrasados_m = int((df_marcos["status_marco"] == "Atrasado").sum())
pct_atr    = atrasados_m / total_m * 100 if total_m > 0 else 0
ma1, ma2, ma3 = st.columns(3)
ma1.metric("Total de Marcos", total_m)
ma2.metric("Marcos Atrasados", atrasados_m)
ma3.metric("% Atrasados", f"{pct_atr:.1f}%")
df_marcos_disp = df_marcos[df_marcos["data_prevista"].notna()].copy()
st.dataframe(
    df_marcos_disp[["nome_projeto", "marco", "data_prevista", "data_realizada", "desvio_dias", "status_marco"]]
    .rename(columns={
        "nome_projeto": "Projeto", "marco": "Marco",
        "data_prevista": "Previsto", "data_realizada": "Realizado",
        "desvio_dias": "Desvio (d)", "status_marco": "Status",
    }),
    use_container_width=True,
)
st.divider()

# ── 5. Custos por Projeto ─────────────────────────────────────────────────────
st.subheader("💰 5. Custos por Projeto")
df_cat = calcular_custos_por_categoria(df_custos_f)
if df_cat.empty:
    st.info("Sem dados de custo para os filtros selecionados.")
else:
    nomes = df_f[["projeto", "nome_projeto"]].drop_duplicates()
    df_cat = df_cat.merge(nomes, on="projeto", how="left")
    st.plotly_chart(charts.grafico_custos_empilhados(df_cat), use_container_width=True)
st.divider()

# ── 6. Distribuição de Custos ─────────────────────────────────────────────────
st.subheader("🍩 6. Distribuição de Custos")
if not df_cat.empty:
    st.plotly_chart(charts.grafico_distribuicao_custos(df_cat), use_container_width=True)
st.divider()

# ── 7. Consumo de Recursos ────────────────────────────────────────────────────
st.subheader("👥 7. Consumo de Recursos")
df_rec = calcular_recursos(df_f, df_horas_f)
if df_rec.empty:
    st.info("Sem dados de horas para os filtros selecionados.")
else:
    st.dataframe(
        df_rec[["nome_projeto", "horas_total", "n_colaboradores", "horas_por_colaborador"]].rename(columns={
            "nome_projeto": "Projeto", "horas_total": "Horas Totais",
            "n_colaboradores": "Colaboradores", "horas_por_colaborador": "Horas/Colaborador",
        }),
        use_container_width=True,
        column_config={
            "Horas Totais": st.column_config.NumberColumn(format="%.0f h"),
            "Horas/Colaborador": st.column_config.NumberColumn(format="%.1f h"),
        },
    )
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("**🏆 Top 5 — Projetos por horas**")
        for _, row in df_rec.nlargest(5, "horas_total").iterrows():
            st.markdown(f"- {row['nome_projeto']}: **{row['horas_total']:.0f} h**")
    with r2:
        st.markdown("**🏆 Top 5 — Colaboradores por horas**")
        if not df_horas_f.empty:
            top_c = df_horas_f.groupby("nome")["hs_nor"].sum().nlargest(5).reset_index()
            for _, row in top_c.iterrows():
                st.markdown(f"- {row['nome']}: **{row['hs_nor']:.0f} h**")
st.divider()

# ── 8. Burn Rate ──────────────────────────────────────────────────────────────
st.subheader("🔥 8. Burn Rate")
if not df_custos_f.empty and "mes_ref" in df_custos_f.columns:
    df_br = calcular_burn_rate(df_custos_f)
    if not df_br.empty:
        st.plotly_chart(charts.grafico_burn_rate_temporal(df_br), use_container_width=True)
    else:
        st.info("Sem dados mensais suficientes.")
else:
    st.info("Sem dados de custo mensais para exibir burn rate.")
st.divider()

# ── 9. Forecast de Prazo ──────────────────────────────────────────────────────
st.subheader("📅 9. Forecast de Prazo")
df_fp = calcular_forecast_prazo(df_f, df_marcos)
st.dataframe(
    df_fp.rename(columns={
        "nome_projeto": "Projeto", "data_planejada": "Data Planejada",
        "atraso_medio_dias": "Atraso Médio (d)", "forecast": "Forecast", "desvio_total": "Desvio (d)",
    }),
    use_container_width=True,
)
st.divider()

# ── 10. Forecast de Custo (EAC) ───────────────────────────────────────────────
st.subheader("💡 10. Forecast de Custo (EAC)")
df_fc = calcular_forecast_custo(df_f, df_marcos)
st.dataframe(
    df_fc.rename(columns={
        "nome_projeto": "Projeto", "custo_atual": "Custo Atual",
        "pct_concluido": "% Concluído", "eac": "EAC",
        "orcamento": "Orçamento", "desvio_eac_pct": "Desvio EAC (%)",
    }),
    use_container_width=True,
    column_config={
        "Custo Atual": st.column_config.NumberColumn(format="R$ %.0f"),
        "EAC":         st.column_config.NumberColumn(format="R$ %.0f"),
        "Orçamento":   st.column_config.NumberColumn(format="R$ %.0f"),
        "% Concluído": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1),
        "Desvio EAC (%)": st.column_config.NumberColumn(format="%.1f%%"),
    },
)
st.divider()

# ── 11. Matriz Executiva ──────────────────────────────────────────────────────
st.subheader("🎯 11. Matriz Executiva — Prazo × Custo")
df_matriz = calcular_matriz_prazo_custo(df_fp, df_fc)
if df_matriz.empty:
    st.info("Dados insuficientes para a matriz. Cadastre orçamentos e marcos nos projetos.")
else:
    st.plotly_chart(charts.grafico_matriz_executiva(df_matriz), use_container_width=True)
```

- [ ] **Step 2: Verificar importações**

```bash
python -c "
import sys; sys.path.insert(0, 'dashboard_projetos')
import ast, pathlib
src = pathlib.Path('dashboard_projetos/pages/5_dashboard_executivo.py').read_text(encoding='utf-8')
ast.parse(src)
print('Sintaxe OK')
"
```
Esperado: `Sintaxe OK`

- [ ] **Step 3: Commit**

```bash
git add dashboard_projetos/pages/5_dashboard_executivo.py
git commit -m "feat: página 5_dashboard_executivo com 11 seções"
```

---

### Task 8: Registrar rota em `app.py`

**Files:**
- Modify: `dashboard_projetos/app.py`

- [ ] **Step 1: Adicionar entrada no menu**

Localizar o bloco `pages` em `app.py` (linha ~113) e substituir:

```python
    "📊 Análises": [
        st.Page(str(ROOT / "pages" / "4_visao_executiva.py"), title="Visão Executiva", icon="🧭"),
        st.Page(str(ROOT / "pages" / "2_dashboard.py"), title="Dashboard Financeiro", icon="📊"),
        st.Page(str(ROOT / "pages" / "3_projetos.py"),  title="Andamento dos Projetos", icon="📈"),
    ],
```

por:

```python
    "📊 Análises": [
        st.Page(str(ROOT / "pages" / "4_visao_executiva.py"),      title="Visão Executiva",            icon="🧭"),
        st.Page(str(ROOT / "pages" / "5_dashboard_executivo.py"),  title="Dashboard Executivo",        icon="📋"),
        st.Page(str(ROOT / "pages" / "2_dashboard.py"),            title="Dashboard Financeiro",       icon="📊"),
        st.Page(str(ROOT / "pages" / "3_projetos.py"),             title="Andamento dos Projetos",     icon="📈"),
    ],
```

- [ ] **Step 2: Verificar sintaxe de app.py**

```bash
python -c "
import ast, pathlib
src = pathlib.Path('dashboard_projetos/app.py').read_text(encoding='utf-8')
ast.parse(src)
print('Sintaxe OK')
"
```

- [ ] **Step 3: Testar localmente**

```bash
cd dashboard_projetos && streamlit run app.py
```

Verificar:
- Menu lateral mostra "Dashboard Executivo" com ícone 📋
- Página carrega sem erros
- KPIs aparecem na seção 1
- Gráficos renderizam nas seções 3, 5, 6, 8, 11
- Filtros de categoria e colaborador aparecem na sidebar

- [ ] **Step 4: Commit final**

```bash
git add dashboard_projetos/app.py
git commit -m "feat: adiciona Dashboard Executivo ao menu de navegação"
```

- [ ] **Step 5: Resumo da branch para avaliação**

```bash
git log main..feat/dashboard-executivo --oneline
```

Esperado (8 commits):
```
feat: adiciona Dashboard Executivo ao menu de navegação
feat: página 5_dashboard_executivo com 11 seções
feat: 5 novos gráficos para dashboard executivo em charts.py
feat: resumo executivo, status projetos, custos por categoria e recursos com TDD
feat: forecast de prazo, custo (EAC) e matriz executiva com TDD
feat: calcular_burn_rate com TDD
feat: calcular_marcos com pesos configuráveis e TDD
feat: categorizar_conta com TDD
chore: scaffold dashboard executivo files
```

Quando aprovado localmente, fazer merge na `main`:
```bash
git checkout main && git merge feat/dashboard-executivo && git push
```
