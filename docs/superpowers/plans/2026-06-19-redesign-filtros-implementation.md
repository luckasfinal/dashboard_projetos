# Redesign dos filtros (Dashboard / Andamento dos Projetos) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar a parede de "pills" nos filtros de Projetos/Mês (causada pelo default "tudo selecionado") e remover a duplicação do bloco de filtros entre `pages/2_dashboard.py` e `pages/3_projetos.py`.

**Architecture:** Extrair a lógica de filtragem para uma função pura `aplicar_filtros` (testável via pytest, sem Streamlit) e a renderização da sidebar para `render_filtros_sidebar` (chama `aplicar_filtros` internamente), ambas em `utils/data_processor.py`. As duas páginas passam a chamar só `render_filtros_sidebar`.

**Tech Stack:** Python, pandas, Streamlit, pytest.

## Global Constraints

- Seleção vazia em qualquer um dos 4 filtros (Projetos, Ano, Mês, Status) significa "sem filtro / mostra tudo" — convenção única para os quatro.
- `Projetos` e `Mês` iniciam vazios por padrão; `Ano` e `Status` mantêm os defaults curados já existentes (`anos_default`, `status_ativos`).
- O botão "Limpar filtros" zera os 4 filtros (`[]`).
- Nenhuma mudança de layout/posição da sidebar nem no seletor de projeto único da página Orçamentos.
- Repositório: `dashboard_projetos/` é a raiz do app Streamlit; todos os caminhos abaixo são relativos a ela.

---

### Task 1: `aplicar_filtros` — lógica pura de filtragem

**Files:**
- Modify: `utils/data_processor.py` (adicionar a função, próximo a `validar_colunas`)
- Test: `tests/test_data_processor_filtros.py` (criar)

**Interfaces:**
- Produces: `aplicar_filtros(df: pd.DataFrame, df_custos_raw: pd.DataFrame, projetos_sel: list, anos_sel: list, meses_sel: list, status_sel: list) -> pd.DataFrame`

- [ ] **Step 1: Escrever os testes (devem falhar)**

Criar `tests/test_data_processor_filtros.py`:

```python
import pandas as pd
from utils.data_processor import aplicar_filtros


def _df_exemplo():
    df = pd.DataFrame({
        "projeto": ["100150001", "100150002", "100150003"],
        "nome_projeto": ["100150001 Alpha", "100150002 Beta", "100150003 Gama"],
        "status_projeto": ["Viabilizado", "Lançado", "Cancelado"],
    })
    df_custos_raw = pd.DataFrame({
        "centro_de_custo": ["100150001", "100150001", "100150002", "100150003"],
        "ano": ["2025", "2026", "2026", "2025"],
        "mes": ["Dezembro", "Janeiro", "Janeiro", "Março"],
    })
    return df, df_custos_raw


def test_sem_selecao_retorna_tudo():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, [], [], [], [])
    assert len(resultado) == 3


def test_filtra_por_projeto():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, ["100150001 Alpha"], [], [], [])
    assert resultado["projeto"].tolist() == ["100150001"]


def test_filtra_por_ano():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, [], ["2026"], [], [])
    assert set(resultado["projeto"]) == {"100150001", "100150002"}


def test_filtra_por_mes():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, [], [], ["Janeiro"], [])
    assert set(resultado["projeto"]) == {"100150001", "100150002"}


def test_filtra_por_status():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, [], [], [], ["Viabilizado", "Cancelado"])
    assert set(resultado["projeto"]) == {"100150001", "100150003"}


def test_combina_multiplos_criterios_com_and():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, [], ["2026"], [], ["Viabilizado"])
    assert resultado["projeto"].tolist() == ["100150001"]
```

- [ ] **Step 2: Rodar e confirmar a falha (RED)**

Run: `python -m pytest tests/test_data_processor_filtros.py -v`
Expected: `ImportError: cannot import name 'aplicar_filtros' from 'utils.data_processor'`

- [ ] **Step 3: Implementar `aplicar_filtros`**

Em `utils/data_processor.py`, adicionar logo após `validar_colunas` (antes do comentário `# Agregação completa (lê do banco)`):

```python
def aplicar_filtros(
    df: pd.DataFrame,
    df_custos_raw: pd.DataFrame,
    projetos_sel: list,
    anos_sel: list,
    meses_sel: list,
    status_sel: list,
) -> pd.DataFrame:
    """Aplica os 4 critérios de filtro (Projetos, Ano, Mês, Status).
    Seleção vazia em qualquer critério = não filtra por ele (mostra tudo).
    """
    df_f = df.copy()
    if projetos_sel:
        df_f = df_f[df_f["nome_projeto"].isin(projetos_sel)]
    if anos_sel and "ano" in df_custos_raw.columns:
        cc_anos = df_custos_raw[df_custos_raw["ano"].astype(str).isin(anos_sel)]["centro_de_custo"].unique()
        df_f = df_f[df_f["projeto"].isin(cc_anos)]
    if meses_sel and "mes" in df_custos_raw.columns:
        cc_meses = df_custos_raw[df_custos_raw["mes"].astype(str).isin(meses_sel)]["centro_de_custo"].unique()
        df_f = df_f[df_f["projeto"].isin(cc_meses)]
    if status_sel and "status_projeto" in df_f.columns:
        df_f = df_f[df_f["status_projeto"].isin(status_sel)]
    return df_f
```

- [ ] **Step 4: Rodar e confirmar que passa (GREEN)**

Run: `python -m pytest tests/test_data_processor_filtros.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add utils/data_processor.py tests/test_data_processor_filtros.py
git commit -m "feat: extrai aplicar_filtros como funcao pura testavel"
```

---

### Task 2: `render_filtros_sidebar` + wire em `pages/2_dashboard.py`

**Files:**
- Modify: `utils/data_processor.py` (adicionar a função, depois de `aplicar_filtros`)
- Modify: `pages/2_dashboard.py:10-14` (import) e `:48-92` (bloco de filtros)

**Interfaces:**
- Consumes: `aplicar_filtros(...)` (Task 1), `anos_default(lista_anos) -> list`, `status_ativos(lista_status) -> list` (já existentes em `utils/data_processor.py`)
- Produces: `render_filtros_sidebar(df: pd.DataFrame, df_custos_raw: pd.DataFrame) -> pd.DataFrame`

- [ ] **Step 1: Implementar `render_filtros_sidebar`**

Em `utils/data_processor.py`, adicionar logo após `aplicar_filtros`:

```python
def render_filtros_sidebar(df: pd.DataFrame, df_custos_raw: pd.DataFrame) -> pd.DataFrame:
    """Renderiza os 4 filtros (Projetos, Ano, Mês, Status) na sidebar e
    retorna o df já filtrado. Usa st.session_state para persistir as
    escolhas entre as páginas Dashboard e Andamento dos Projetos (mesmas
    chaves). Seleção vazia em qualquer filtro = sem filtro (mostra tudo).
    """
    lista_projetos = sorted(df["nome_projeto"].dropna().unique().tolist())
    lista_anos     = sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist()) if "ano" in df_custos_raw.columns else []
    lista_meses    = sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist()) if "mes" in df_custos_raw.columns else []
    lista_status   = sorted(df["status_projeto"].dropna().unique().tolist()) if "status_projeto" in df.columns else []

    if "filtro_projetos" not in st.session_state: st.session_state["filtro_projetos"] = []
    if "filtro_anos"     not in st.session_state: st.session_state["filtro_anos"]     = anos_default(lista_anos)
    if "filtro_meses"    not in st.session_state: st.session_state["filtro_meses"]    = []
    if "filtro_status"   not in st.session_state: st.session_state["filtro_status"]   = status_ativos(lista_status)

    st.session_state["filtro_projetos"] = [p for p in st.session_state["filtro_projetos"] if p in lista_projetos]
    st.session_state["filtro_anos"]     = [a for a in st.session_state["filtro_anos"]     if a in lista_anos]
    st.session_state["filtro_meses"]    = [m for m in st.session_state["filtro_meses"]    if m in lista_meses]
    st.session_state["filtro_status"]   = [s for s in st.session_state["filtro_status"]   if s in lista_status]

    with st.sidebar:
        st.header("🔍 Filtros")

        projetos_selecionados = st.multiselect("Projetos:", options=lista_projetos,
            default=st.session_state["filtro_projetos"], key="filtro_projetos")
        st.caption(f"{len(projetos_selecionados)} de {len(lista_projetos)} selecionados"
                   if projetos_selecionados else f"Mostrando todos os {len(lista_projetos)} projetos")

        anos_selecionados = st.multiselect("Ano:", options=lista_anos,
            default=st.session_state["filtro_anos"], key="filtro_anos")
        st.caption(f"{len(anos_selecionados)} de {len(lista_anos)} selecionados"
                   if anos_selecionados else f"Mostrando todos os {len(lista_anos)} anos")

        meses_selecionados = st.multiselect("Mês:", options=lista_meses,
            default=st.session_state["filtro_meses"], key="filtro_meses")
        st.caption(f"{len(meses_selecionados)} de {len(lista_meses)} selecionados"
                   if meses_selecionados else f"Mostrando todos os {len(lista_meses)} meses")

        status_selecionados = st.multiselect("Status do Projeto:", options=lista_status,
            default=st.session_state["filtro_status"], key="filtro_status")
        st.caption(f"{len(status_selecionados)} de {len(lista_status)} selecionados"
                   if status_selecionados else f"Mostrando todos os {len(lista_status)} status")

        if st.button("🔄 Limpar filtros", use_container_width=True):
            st.session_state["filtro_projetos"] = []
            st.session_state["filtro_anos"]     = []
            st.session_state["filtro_meses"]    = []
            st.session_state["filtro_status"]   = []
            st.rerun()

    return aplicar_filtros(
        df, df_custos_raw,
        projetos_selecionados, anos_selecionados, meses_selecionados, status_selecionados,
    )
```

- [ ] **Step 2: Atualizar o import em `pages/2_dashboard.py:10-14`**

Substituir:

```python
from utils.data_processor import (
    agregar_tudo, formata_brl, formata_brl_curto, cor_status, cor_status_projeto,
    render_selo_dados, aviso_truncamento, detectar_excecoes,
    status_ativos, anos_default,
)
```

Por:

```python
from utils.data_processor import (
    agregar_tudo, formata_brl, formata_brl_curto, cor_status, cor_status_projeto,
    render_selo_dados, aviso_truncamento, detectar_excecoes,
    render_filtros_sidebar,
)
```

- [ ] **Step 3: Substituir o bloco de filtros em `pages/2_dashboard.py:48-92`**

Remover linhas 48 a 92 (de `# ── Filtros persistentes ──...` até o fim do bloco `if status_selecionados and ...`) e substituir por:

```python
# ── Filtros ───────────────────────────────────────────────────────────────────
df_f = render_filtros_sidebar(df_dashboard, df_custos_raw)
```

As linhas seguintes (hoje 94-96: cálculo de `df_c_f`, `df_h_f`, `mes_col`) permanecem inalteradas, agora referenciando o `df_f` retornado por `render_filtros_sidebar`.

- [ ] **Step 4: Verificação manual no navegador**

```bash
python -m streamlit run app.py --server.headless true
```

Abrir `http://localhost:8501`, ir para **Dashboard Financeiro** e confirmar:
- O multiselect "Projetos:" inicia **sem pills**, com a legenda "Mostrando todos os N projetos".
- O multiselect "Mês:" inicia **sem pills**, com legenda equivalente.
- "Ano:" e "Status do Projeto:" continuam com seus defaults de antes (ano corrente / status ativos) e legenda correspondente.
- Selecionar um projeto específico filtra o dashboard corretamente.
- Clicar "🔄 Limpar filtros" zera os 4 filtros (sem pills em nenhum) e o dashboard volta a mostrar tudo.

Parar o servidor depois de validar.

- [ ] **Step 5: Commit**

```bash
git add utils/data_processor.py pages/2_dashboard.py
git commit -m "feat: render_filtros_sidebar com defaults vazios para Projetos/Mes (Dashboard)"
```

---

### Task 3: Wire em `pages/3_projetos.py` e remover duplicação

**Files:**
- Modify: `pages/3_projetos.py:11-16` (import) e `:90-134` (bloco de filtros)

**Interfaces:**
- Consumes: `render_filtros_sidebar(df: pd.DataFrame, df_custos_raw: pd.DataFrame) -> pd.DataFrame` (Task 2)

- [ ] **Step 1: Atualizar o import em `pages/3_projetos.py:11-16`**

Substituir:

```python
from utils.data_processor import (
    agregar_tudo, formata_brl, formata_brl_curto, cor_status, cor_status_projeto,
    badge_status_projeto, agrupar_por_nome_projeto, render_selo_dados,
    aviso_truncamento, detectar_excecoes, render_faixa_alertas, projecao_burn_rate,
    status_ativos, anos_default, rotulo_consumo,
)
```

Por:

```python
from utils.data_processor import (
    agregar_tudo, formata_brl, formata_brl_curto, cor_status, cor_status_projeto,
    badge_status_projeto, agrupar_por_nome_projeto, render_selo_dados,
    aviso_truncamento, detectar_excecoes, render_faixa_alertas, projecao_burn_rate,
    render_filtros_sidebar, rotulo_consumo,
)
```

- [ ] **Step 2: Substituir o bloco de filtros em `pages/3_projetos.py:90-134`**

Remover linhas 90 a 134 (de `# ── Filtros persistentes ──...` até o fim do bloco `if status_selecionados and ...`) e substituir por:

```python
# ── Aplicação dos filtros ─────────────────────────────────────────────────────
df_f = render_filtros_sidebar(df, df_custos_raw)
```

As linhas seguintes (hoje a partir de 136: `if df_f.empty:`) permanecem inalteradas.

- [ ] **Step 3: Verificação manual no navegador**

```bash
python -m streamlit run app.py --server.headless true
```

Abrir `http://localhost:8501`, ir para **Andamento dos Projetos** e confirmar:
- Mesmo comportamento validado na Task 2 (sem pills em Projetos/Mês, legendas corretas, filtro funciona, "Limpar filtros" zera tudo).
- Navegar entre **Dashboard Financeiro** e **Andamento dos Projetos** e confirmar que a seleção de filtros persiste corretamente entre as duas páginas (mesmo `session_state`).

Parar o servidor depois de validar.

- [ ] **Step 4: Rodar a suíte completa de testes**

Run: `python -m pytest tests/ -v`
Expected: todos os testes passam (incluindo os 6 novos de `test_data_processor_filtros.py`).

- [ ] **Step 5: Commit**

```bash
git add pages/3_projetos.py
git commit -m "feat: usa render_filtros_sidebar em Andamento dos Projetos, remove duplicacao"
```
