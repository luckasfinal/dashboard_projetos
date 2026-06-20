# Visão Executiva Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar uma página de portfólio que classifica cada projeto em risco Alto/Médio/Baixo combinando projeção de custo (já existente via `projecao_burn_rate`) e atraso em qualquer marco do cronograma (hoje só checado no marco final), para varredura rápida por gerentes de negócio.

**Architecture:** Uma função pura `calcular_risco_portfolio` em `utils/data_processor.py` (testável via pytest) calcula o risco por projeto; uma página nova `pages/4_visao_executiva.py` reaproveita os filtros e componentes já existentes para renderizar o resultado.

**Tech Stack:** Python, pandas, Streamlit, pytest.

## Global Constraints

- Risco de custo: projeção `< 80%` do orçamento = saudável, `80–100%` = atenção, `> 100%` = estouro.
- Risco de prazo: qualquer marco com atraso `> 0` dias já conta como risco, sem tolerância — verificado nos 4 marcos com par previsto/realizado (Viabilidade, Qualidade, Aprovação para Lançamento, Lançamento); `data_inicio` não tem par "real" e não é verificado.
- Risco combinado por projeto: 🔴 Alto se (estouro de custo OU algum atraso); 🟡 Médio se (custo entre 80–100% E sem atraso); 🟢 Baixo nos demais casos (inclui "sem orçamento cadastrado" quando também não há atraso).
- Não alterar `pages/2_dashboard.py`, `pages/3_projetos.py`, nem os limiares já usados em `cor_status`/`rotulo_consumo` — a nova classificação é isolada nesta página nova.
- Cards grandes só para risco Alto/Médio; Baixo risco fica numa lista compacta dentro de um `st.expander`.
- Repositório: `dashboard_projetos/` é a raiz do app Streamlit; todos os caminhos abaixo são relativos a ela.

---

### Task 1: `calcular_risco_portfolio` — classificação pura de risco

**Files:**
- Modify: `utils/data_processor.py` (adicionar logo após `projecao_burn_rate`, antes do comentário `# Defaults de filtros curados (Roadmap 4.2)`)
- Test: `tests/test_data_processor_risco.py` (criar)

**Interfaces:**
- Consumes: `projecao_burn_rate(row, df_custos_proj) -> dict` (já existe em `utils/data_processor.py`, retorna `{"realizado", "ritmo_mensal", "meses_decorridos", "meses_restantes", "projecao_final", "orcamento", "pct_projetado", "vai_estourar", "status"}`, onde `pct_projetado` é `None` somente quando não há orçamento cadastrado)
- Produces: `calcular_risco_portfolio(df: pd.DataFrame, df_custos_raw: pd.DataFrame) -> pd.DataFrame` com colunas `["projeto", "nome_projeto", "nivel_risco", "motivos", "pct_projetado", "dias_atraso_max", "orcamento"]`, ordenado com `nivel_risco == "alto"` primeiro, depois `"medio"`, depois `"baixo"` (dentro de cada nível, por `pct_projetado` decrescente)

- [ ] **Step 1: Escrever os testes (devem falhar)**

Criar `tests/test_data_processor_risco.py`:

```python
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
```

- [ ] **Step 2: Rodar e confirmar a falha (RED)**

Run: `python -m pytest tests/test_data_processor_risco.py -v`
Expected: `ImportError: cannot import name 'calcular_risco_portfolio' from 'utils.data_processor'`

- [ ] **Step 3: Implementar `calcular_risco_portfolio`**

Em `utils/data_processor.py`, adicionar logo após o fim de `projecao_burn_rate` (antes do comentário `# Defaults de filtros curados (Roadmap 4.2)`):

```python
MARCOS_RISCO = [
    ("prev_viabilidade", "real_viabilidade", "Viabilidade"),
    ("prev_qualidade", "real_qualidade", "Qualidade"),
    ("prev_aprov_lancamento", "real_aprov_lancamento", "Aprovação para Lançamento"),
    ("prev_lancamento", "real_lancamento", "Lançamento"),
]


def _parse_data_marco(val):
    from datetime import datetime as _dt
    if not val or str(val) in ("0", "None", "nan", ""):
        return None
    try:
        return _dt.strptime(str(val)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def calcular_risco_portfolio(df: pd.DataFrame, df_custos_raw: pd.DataFrame) -> pd.DataFrame:
    """Classifica cada projeto em nivel_risco ('alto'/'medio'/'baixo'), combinando
    a projeção de custo (projecao_burn_rate) com atraso em qualquer marco do
    cronograma. Retorna um DataFrame ordenado por risco (alto primeiro).
    """
    from datetime import datetime as _dt

    colunas = ["projeto", "nome_projeto", "nivel_risco", "motivos", "pct_projetado", "dias_atraso_max", "orcamento"]
    if df is None or df.empty:
        return pd.DataFrame(columns=colunas)

    hoje = _dt.today().date()
    linhas = []

    for _, row in df.iterrows():
        projeto = row.get("projeto")
        nome_projeto = row.get("nome_projeto", projeto)
        orcamento = row.get("orcamento", 0) or 0
        motivos = []

        if df_custos_raw is not None and not df_custos_raw.empty and "centro_de_custo" in df_custos_raw.columns:
            df_c_proj = df_custos_raw[df_custos_raw["centro_de_custo"] == projeto]
        else:
            df_c_proj = pd.DataFrame()
        proj_burn = projecao_burn_rate(row, df_c_proj)
        pct = proj_burn["pct_projetado"]

        if pct is None:
            risco_custo = "indeterminado"
            motivos.append("Sem orçamento cadastrado")
        elif pct > 100:
            risco_custo = "alto"
            motivos.append(f"Projeção de custo: {pct:.0f}% do orçamento")
        elif pct >= 80:
            risco_custo = "medio"
            motivos.append(f"Projeção de custo: {pct:.0f}% do orçamento")
        else:
            risco_custo = "baixo"

        dias_atraso_max = 0
        for col_prev, col_real, label in MARCOS_RISCO:
            prev_d = _parse_data_marco(row.get(col_prev))
            if prev_d is None:
                continue
            real_d = _parse_data_marco(row.get(col_real))
            ref = real_d if real_d else hoje
            if ref > prev_d:
                dias = (ref - prev_d).days
                motivos.append(f"{label} atrasado(a) {dias} dia(s)")
                dias_atraso_max = max(dias_atraso_max, dias)

        if risco_custo == "alto" or dias_atraso_max > 0:
            nivel_risco = "alto"
        elif risco_custo == "medio":
            nivel_risco = "medio"
        else:
            nivel_risco = "baixo"

        linhas.append({
            "projeto": projeto,
            "nome_projeto": nome_projeto,
            "nivel_risco": nivel_risco,
            "motivos": motivos,
            "pct_projetado": pct,
            "dias_atraso_max": dias_atraso_max,
            "orcamento": orcamento,
        })

    resultado = pd.DataFrame(linhas, columns=colunas)
    ordem = {"alto": 0, "medio": 1, "baixo": 2}
    resultado["_ordem"] = resultado["nivel_risco"].map(ordem)
    resultado = resultado.sort_values(
        ["_ordem", "pct_projetado"], ascending=[True, False], na_position="last"
    ).drop(columns="_ordem").reset_index(drop=True)
    return resultado
```

`pd` já está importado no topo do arquivo (`import pandas as pd`); `datetime` é importado localmente dentro de cada função que precisa (mesmo padrão já usado em `projecao_burn_rate` e `detectar_excecoes`), por isso não é necessário tocar nos imports do topo do arquivo.

- [ ] **Step 4: Rodar e confirmar que passa (GREEN)**

Run: `python -m pytest tests/test_data_processor_risco.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add utils/data_processor.py tests/test_data_processor_risco.py
git commit -m "feat: adiciona calcular_risco_portfolio (risco combinado de custo e prazo)"
```

---

### Task 2: Página `pages/4_visao_executiva.py`

**Files:**
- Create: `pages/4_visao_executiva.py`
- Modify: `app.py:113-122` (registro de páginas)

**Interfaces:**
- Consumes: `agregar_tudo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]`, `render_filtros_sidebar(df, df_custos_raw) -> pd.DataFrame`, `formata_brl(valor: float) -> str`, `calcular_risco_portfolio(df, df_custos_raw) -> pd.DataFrame` (Task 1) — todas já existentes/criadas em `utils/data_processor.py`

- [ ] **Step 1: Criar `pages/4_visao_executiva.py`**

```python
import sys
from pathlib import Path
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from utils.db import init_db
from utils.data_processor import (
    agregar_tudo, formata_brl, render_filtros_sidebar, calcular_risco_portfolio,
)

init_db()

st.title("🧭 Visão Executiva")
st.caption("Quais projetos precisam de atenção agora — risco combinado de custo e prazo.")

df_dashboard, df_custos_raw, df_horas_raw = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

df_f = render_filtros_sidebar(df_dashboard, df_custos_raw)

if df_f.empty:
    st.info("Nenhum projeto encontrado para os filtros selecionados.")
    st.stop()

risco = calcular_risco_portfolio(df_f, df_custos_raw)

n_alto  = int((risco["nivel_risco"] == "alto").sum())
n_medio = int((risco["nivel_risco"] == "medio").sum())
n_baixo = int((risco["nivel_risco"] == "baixo").sum())

c1, c2, c3 = st.columns(3)
c1.metric("🔴 Alto risco", str(n_alto))
c2.metric("🟡 Risco médio", str(n_medio))
c3.metric("🟢 Baixo risco", str(n_baixo))

st.divider()

CORES_RISCO  = {"alto": "#7f1d1d", "medio": "#7c2d12", "baixo": "#14532d"}
ICONES_RISCO = {"alto": "🔴", "medio": "🟡", "baixo": "🟢"}
LABEL_RISCO  = {"alto": "Alto risco", "medio": "Risco médio", "baixo": "Baixo risco"}

destaque = risco[risco["nivel_risco"].isin(["alto", "medio"])]

if destaque.empty:
    st.success("✅ Nenhum projeto em risco alto ou médio nos filtros selecionados.")
else:
    for _, r in destaque.iterrows():
        cor    = CORES_RISCO[r["nivel_risco"]]
        icone  = ICONES_RISCO[r["nivel_risco"]]
        label  = LABEL_RISCO[r["nivel_risco"]]
        motivos_html = "<br>".join(r["motivos"]) if r["motivos"] else "—"
        pct_txt = f"{r['pct_projetado']:.0f}% do orçamento projetado" if r["pct_projetado"] is not None else "Projeção indisponível"
        st.markdown(f"""
        <div style="background:{cor}22;border-left:4px solid {cor};border-radius:8px;
                    padding:12px 16px;margin-bottom:10px">
            <div style="font-weight:700">{icone} {r['nome_projeto']} — {label}</div>
            <div style="opacity:.85;margin-top:4px;font-size:13px">
                Orçamento: {formata_brl(r['orcamento'])} · {pct_txt}
            </div>
            <div style="opacity:.85;margin-top:6px;font-size:14px">{motivos_html}</div>
        </div>
        """, unsafe_allow_html=True)

baixo = risco[risco["nivel_risco"] == "baixo"]
if not baixo.empty:
    with st.expander(f"🟢 Ver {len(baixo)} projeto(s) em baixo risco"):
        for _, r in baixo.iterrows():
            st.markdown(f"- {r['nome_projeto']}")

st.divider()

csv_export = risco.copy()
csv_export["motivos"] = csv_export["motivos"].apply(lambda m: "; ".join(m) if m else "")
st.download_button(
    "⬇️ Exportar CSV",
    csv_export.to_csv(index=False).encode("utf-8"),
    "visao_executiva_riscos.csv",
    "text/csv",
    use_container_width=True,
)
```

- [ ] **Step 2: Registrar a página em `app.py`**

Em `app.py`, localizar o bloco (linhas 113-122):

```python
pages = {
    "📤 Dados": [
        st.Page(str(ROOT / "pages" / "0_orcamento.py"), title="Orçamentos",          icon="📋"),
        st.Page(str(ROOT / "pages" / "1_upload.py"),    title="Upload de Arquivos",   icon="📤"),
    ],
    "📊 Análises": [
        st.Page(str(ROOT / "pages" / "2_dashboard.py"), title="Dashboard Financeiro", icon="📊"),
        st.Page(str(ROOT / "pages" / "3_projetos.py"),  title="Andamento dos Projetos", icon="📈"),
    ],
}
```

Substituir por (adiciona a Visão Executiva como primeiro item de "📊 Análises", já que é o ponto de entrada para decisão rápida):

```python
pages = {
    "📤 Dados": [
        st.Page(str(ROOT / "pages" / "0_orcamento.py"), title="Orçamentos",          icon="📋"),
        st.Page(str(ROOT / "pages" / "1_upload.py"),    title="Upload de Arquivos",   icon="📤"),
    ],
    "📊 Análises": [
        st.Page(str(ROOT / "pages" / "4_visao_executiva.py"), title="Visão Executiva", icon="🧭"),
        st.Page(str(ROOT / "pages" / "2_dashboard.py"), title="Dashboard Financeiro", icon="📊"),
        st.Page(str(ROOT / "pages" / "3_projetos.py"),  title="Andamento dos Projetos", icon="📈"),
    ],
}
```

- [ ] **Step 3: Verificação manual no navegador**

```bash
python -m streamlit run app.py --server.headless true
```

Abrir `http://localhost:8501`, ir para **Visão Executiva** e confirmar:
- Os 3 contadores (Alto/Médio/Baixo) somam o total de projetos visíveis nos filtros.
- Só aparecem cards grandes para projetos em risco Alto ou Médio, com motivos legíveis.
- Projetos em risco Baixo aparecem na lista compacta dentro do expander, não como cards.
- Ordenação: cards de risco Alto aparecem antes dos de risco Médio.
- Trocar os filtros na sidebar (ex: selecionar um projeto específico) atualiza a Visão Executiva corretamente.
- "⬇️ Exportar CSV" baixa um arquivo com todas as colunas, incluindo `motivos` como texto.

Parar o servidor depois de validar.

- [ ] **Step 4: Rodar a suíte completa de testes**

Run: `python -m pytest tests/ -v`
Expected: todos os testes passam (incluindo os 6 novos de `test_data_processor_risco.py`).

- [ ] **Step 5: Commit**

```bash
git add app.py pages/4_visao_executiva.py
git commit -m "feat: adiciona pagina Visao Executiva (risco combinado de portfolio)"
```
