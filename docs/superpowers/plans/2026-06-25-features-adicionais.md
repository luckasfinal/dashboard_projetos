# Features Adicionais — Fase 2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar 10 features adicionais agrupadas em 3 worktrees paralelas, cobrindo analytics executivos, visualizações de portfólio e persistência de dados.

**Architecture:** Cada agente trabalha em uma worktree git isolada. As funções novas vão em `dashboard_executivo.py` (puras, sem Streamlit). A UI vai nas pages existentes. DB changes vão em `db.py` com migrações idempotentes (`ADD COLUMN IF NOT EXISTS`).

**Tech Stack:** Python 3.11+, Streamlit, pandas, Plotly, PostgreSQL/SQLAlchemy (Supabase), pytest.

## Global Constraints

- Nenhuma nova dependência Python.
- Funções de cálculo: sempre puras, em `dashboard_executivo.py` ou `charts.py`.
- DB changes: sempre idempotentes (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
- Testes: pytest em `dashboard_projetos/tests/`, sem tocar no banco diretamente (usar DataFrames em memória).
- Comandos de teste: rodar de dentro de `dashboard_projetos/`.
- Não implementar: A2 (navigation merge, post-merge task), B4, B6, C1, C3, C4, C5, C7.

---

## Mapa de Agentes

| Agente | Features | Branch |
|---|---|---|
| 1 | A1 (Home) + A6 (CPI) | feature/home-executiva-cpi |
| 2 | A7, B2, B3, B7, C2 | feature/analytics-executivos |
| 3 | A5, B1 | feature/gantt-colaboradores |
| 4 | A3, B5, C6 | feature/db-features-visual |

---

## Agente 2 — Analytics Executivos (A7, B2, B3, B7, C2)

### Task 6: A7 — Burn Rate Deslizante (últimos 3 meses)

**Files:**
- Modify: `dashboard_projetos/utils/dashboard_executivo.py` — `calcular_burn_rate`
- Modify: `dashboard_projetos/pages/5_dashboard_executivo.py` — seção Burn Rate

**Change:** Adicionar coluna `burn_rate_3m` ao DataFrame retornado por `calcular_burn_rate`. Representa a média mensal de custo dos últimos 3 meses com dados (vs. `burn_rate` que é a média acumulada histórica).

```python
# Dentro de calcular_burn_rate, após calcular burn_rate:
def _br3m(grp: pd.DataFrame) -> float:
    last3 = grp.sort_values("mes_ref").tail(3)
    return float(last3["custo_mensal"].mean())

br3m = (
    df.groupby("projeto")
    .apply(_br3m)
    .reset_index(name="burn_rate_3m")
)
df = df.merge(br3m, on="projeto", how="left")
```

**Display:** Na seção "Burn Rate" de `5_dashboard_executivo.py`, após o gráfico existente, adicionar `st.metric` com ritmo atual (3m) vs. histórico. Caption: "Ritmo recente (últ. 3 meses) vs. média histórica."

- [ ] Testes em `tests/test_dashboard_executivo.py`
- [ ] Commit: `feat: burn rate deslizante (3 meses) em calcular_burn_rate`

---

### Task 7: B2 — Benchmarking por Segmento

**Files:**
- Modify: `dashboard_projetos/utils/dashboard_executivo.py` — nova função
- Modify: `dashboard_projetos/pages/5_dashboard_executivo.py` — Tab Estratégico

**New function:**
```python
def calcular_benchmarking_segmento(df_f: pd.DataFrame) -> pd.DataFrame:
    """Agrupa por segmento: n_projetos, consumo_medio_pct, custo_total, horas_total."""
    if df_f.empty or "segmento" not in df_f.columns:
        return pd.DataFrame(columns=["segmento","n_projetos","consumo_medio_pct","custo_total","horas_total"])
    df_seg = df_f[df_f["segmento"].notna() & (df_f["segmento"].astype(str).str.strip() != "")].copy()
    if df_seg.empty:
        return pd.DataFrame(columns=["segmento","n_projetos","consumo_medio_pct","custo_total","horas_total"])
    return (
        df_seg.groupby("segmento")
        .agg(
            n_projetos=("projeto", "count"),
            consumo_medio_pct=("pct_orcamento", "mean"),
            custo_total=("valor_total", "sum"),
            horas_total=("horas_total", "sum"),
        )
        .reset_index()
        .sort_values("custo_total", ascending=False)
    )
```

**Display:** Tab "🎯 Estratégico" de `5_dashboard_executivo.py`, abaixo da matriz existente: tabela + bar chart horizontal de consumo médio por segmento.

- [ ] Testes em `tests/test_dashboard_executivo.py`
- [ ] Commit: `feat: benchmarking por segmento`

---

### Task 8: B3 — Índice de Saúde (0–100)

**Files:**
- Modify: `dashboard_projetos/utils/dashboard_executivo.py` — nova função
- Modify: `dashboard_projetos/pages/5_dashboard_executivo.py` — coluna na tabela Resumo
- Modify: `dashboard_projetos/pages/4_visao_executiva.py` — badge nos cards de projeto

**New function:**
```python
def calcular_indice_saude(pct_orcamento: float, dias_atraso_max: int, status: str = "") -> int:
    """Índice de saúde 0–100. Maior = mais saudável."""
    score = 100
    if pct_orcamento > 100: score -= 20
    elif pct_orcamento > 80: score -= 10
    if dias_atraso_max > 30: score -= 30
    elif dias_atraso_max > 0: score -= 15
    if str(status).strip() == "Stand by": score -= 10
    elif str(status).strip() == "Cancelado": score -= 20
    if 0 < pct_orcamento < 60: score += 10
    return max(0, min(100, score))
```

**Display:**
- Em `5_dashboard_executivo.py` Tab Resumo: nova coluna "Saúde" (0–100) na tabela de status.
- Em `4_visao_executiva.py`: adicionar "Saúde: X/100" no texto dos cards de alto/médio risco.

- [ ] Testes em `tests/test_dashboard_executivo.py`
- [ ] Commit: `feat: índice de saúde por projeto (0-100)`

---

### Task 9: B7 — Ranking Comparativo de Projetos

**Files:**
- Modify: `dashboard_projetos/pages/5_dashboard_executivo.py` — nova seção Tab Resumo

**Feature:** Tabela ordenável por múltiplas colunas mostrando todos os projetos lado a lado:
Nome | Saúde | % Orçamento | Atraso (d) | Horas | Status

Usa `calcular_indice_saude` de B3. Usa os dados já disponíveis em `df_status` (já calculado na página). Adicionar logo acima da tabela de status existente.

```python
# No Tab Resumo, antes da tabela df_status existente:
st.subheader("🏆 Ranking Comparativo")
df_ranking = df_f[["nome_projeto","pct_orcamento","horas_total","status_projeto"]].copy()
df_ranking["saude"] = df_ranking.apply(
    lambda r: calcular_indice_saude(
        float(r.get("pct_orcamento", 0) or 0),
        int(risco[risco["nome_projeto"] == r["nome_projeto"]]["dias_atraso_max"].iloc[0])
        if not risco[risco["nome_projeto"] == r["nome_projeto"]].empty else 0,
        str(r.get("status_projeto", "")),
    ), axis=1
)
# ... sort and display
```

Note: `risco` não está disponível no Tab Resumo. Calcular `dias_atraso_max` a partir de `df_marcos` (disponível). Usar `df_marcos[df_marcos["projeto"]==proj]["desvio_dias"].max()` para projetos com marcos atrasados.

- [ ] Commit: `feat: ranking comparativo de projetos`

---

### Task 10: C2 — Setas de Tendência nos KPIs

**Files:**
- Modify: `dashboard_projetos/pages/2_dashboard.py` — KPI "Realizado Total"

**Feature:** No KPI "💰 Realizado Total" de `2_dashboard.py`, mostrar delta comparando custo do mês mais recente vs. mês anterior (dos dados já filtrados `df_c_f`).

```python
# Após computar total_custo, adicionar:
delta_mes_str = None
if not df_c_f.empty and "mes_ref" in df_c_f.columns:
    meses_ordenados = sorted(df_c_f["mes_ref"].dropna().unique())
    if len(meses_ordenados) >= 2:
        m_atual = meses_ordenados[-1]
        m_ant   = meses_ordenados[-2]
        c_atual = float(df_c_f[df_c_f["mes_ref"] == m_atual]["realizado"].sum())
        c_ant   = float(df_c_f[df_c_f["mes_ref"] == m_ant  ]["realizado"].sum())
        diff    = c_atual - c_ant
        delta_mes_str = f"{formata_brl_curto(diff)} vs {m_ant}"

# Usar delta_mes_str no metric:
l1c2.metric(
    "💰 Realizado Total",
    formata_brl_curto(total_custo),
    delta=delta_mes_str,
    delta_color="inverse",   # aumento = vermelho (custo cresce = atenção)
    help=f"Valor exato: {formata_brl(total_custo)}",
)
```

- [ ] Commit: `feat: tendência mês-a-mês no KPI de custo realizado`

---

## Agente 3 — Gantt + Colaboradores (A5, B1)

### Task 11: A5 — Gantt Simplificado

**Files:**
- Modify: `dashboard_projetos/utils/charts.py` — nova função `grafico_gantt_portfolio`
- Modify: `dashboard_projetos/pages/3_projetos.py` — Tab Resumo, nova seção

**New function in charts.py:**
```python
def grafico_gantt_portfolio(df_f: pd.DataFrame) -> go.Figure:
    from datetime import date as _date
    import plotly.express as px

    def _pd(val):
        if not val or str(val) in ("0","None","nan",""): return None
        try: return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
        except: return None

    linhas = []
    for _, row in df_f.iterrows():
        nome = row.get("nome_projeto", row.get("projeto", "?"))
        ini  = _pd(row.get("data_inicio"))
        lp   = _pd(row.get("prev_lancamento"))
        lr   = _pd(row.get("real_lancamento"))
        if ini is None or lp is None:
            continue
        linhas.append({"Projeto": nome, "Início": str(ini), "Fim": str(lp),  "Tipo": "Planejado"})
        if lr:
            linhas.append({"Projeto": nome, "Início": str(ini), "Fim": str(lr), "Tipo": "Realizado"})

    if not linhas:
        fig = go.Figure()
        fig.update_layout(**LAYOUT_BASE, template="plotly_dark",
            title="<b>Gantt do Portfólio</b>",
            annotations=[{"text": "Sem projetos com início e lançamento previstos cadastrados.",
                          "showarrow": False, "xref": "paper", "yref": "paper", "x": 0.5, "y": 0.5}])
        return fig

    df_span = pd.DataFrame(linhas)
    cores   = {"Planejado": "rgba(76,120,168,0.55)", "Realizado": "rgba(34,197,94,0.6)"}

    fig = px.timeline(
        df_span, x_start="Início", x_end="Fim", y="Projeto",
        color="Tipo", color_discrete_map=cores,
        title="<b>Gantt do Portfólio</b>",
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        **LAYOUT_BASE,
        template="plotly_dark",
        height=max(300, len(df_f) * 45 + 120),
        margin=dict(l=20, r=20, t=44, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.add_vline(x=str(_date.today()), line_dash="dot", line_color="rgba(255,255,255,0.35)", line_width=1.5)
    return fig
```

**Display in 3_projetos.py:** No Tab "📊 Resumo Geral", após a Timeline de Lançamentos existente (`st.divider()` + `st.subheader("🗓️ Gantt do Portfólio")` + `st.plotly_chart(charts.grafico_gantt_portfolio(df_f), ...)`).

- [ ] Testes em `tests/test_charts_gantt.py` (novo arquivo)
- [ ] Commit: `feat: gantt simplificado do portfólio`

---

### Task 12: B1 — Análise de Colaboradores

**Files:**
- Modify: `dashboard_projetos/pages/3_projetos.py` — Tab Resumo, nova seção após Horas por Projeto
- Modify: `dashboard_projetos/utils/charts.py` — nova função `grafico_top_colaboradores`

**New chart in charts.py:**
```python
def grafico_top_colaboradores(df_top: pd.DataFrame) -> go.Figure:
    """Horizontal bar: top colaboradores por horas. df_top colunas: Colaborador, Horas, Projetos."""
    fig = px.bar(
        df_top.sort_values("Horas"),
        x="Horas", y="Colaborador", orientation="h",
        title="<b>Top Colaboradores — Horas</b>",
        color="Horas",
        color_continuous_scale=[[0, "rgba(37,99,235,.25)"], [1, "rgba(37,99,235,.9)"]],
        text="Horas",
    )
    fig.update_traces(texttemplate="%{text:.0f} h", textposition="outside")
    fig.update_layout(**LAYOUT_BASE, template="plotly_dark", margin=_MARGIN,
                      coloraxis_showscale=False)
    return fig
```

**Display in 3_projetos.py Tab Resumo:**
```python
# Após seção "Horas por Projeto":
st.divider()
st.subheader("👥 Análise de Colaboradores")
if not df_h_f.empty and "nome" in df_h_f.columns:
    top_colabs = (
        df_h_f.groupby("nome").agg(
            Horas=("hs_nor", "sum"),
            Projetos=("c_custo", "nunique"),
        ).reset_index().rename(columns={"nome": "Colaborador"})
        .sort_values("Horas", ascending=False).head(10)
    )
    cc1, cc2 = st.columns(2)
    with cc1:
        st.plotly_chart(charts.grafico_top_colaboradores(top_colabs),
                        use_container_width=True, key="top_colabs_resumo")
    with cc2:
        st.markdown("**Distribuição por Colaborador**")
        st.dataframe(
            top_colabs.reset_index(drop=True),
            use_container_width=True, hide_index=True,
            column_config={
                "Horas":    st.column_config.NumberColumn(format="%.0f h"),
                "Projetos": st.column_config.NumberColumn(format="%d"),
            }
        )
else:
    st.caption("ℹ️ Sem dados de horas para os filtros selecionados.")
```

- [ ] Commit: `feat: análise de colaboradores no resumo do portfólio`

---

## Agente 4 — DB Features + Visual (A3, B5, C6)

### Task 13: A3 — Histórico de Revisões de Orçamento

**Files:**
- Modify: `dashboard_projetos/utils/db.py` — nova tabela + funções
- Modify: `dashboard_projetos/pages/0_orcamento.py` — exibir histórico
- Modify: `dashboard_projetos/tests/test_db_orcamentos.py` — testes

**New table (in `init_db` or `migrar_db`):**
```sql
CREATE TABLE IF NOT EXISTS historico_orcamentos (
    id SERIAL PRIMARY KEY,
    projeto TEXT NOT NULL,
    campo TEXT NOT NULL,
    valor_anterior TEXT,
    valor_novo TEXT,
    alterado_em TEXT NOT NULL
);
```

**New functions in db.py:**
```python
def registrar_historico_orcamento(projeto: str, campo: str, valor_anterior, valor_novo) -> None:
    """Registra uma alteração de campo no histórico."""
    with _engine().begin() as con:
        con.execute(text("""
            INSERT INTO historico_orcamentos (projeto, campo, valor_anterior, valor_novo, alterado_em)
            VALUES (:p, :c, :va, :vn, :ts)
        """), {"p": projeto, "c": campo, "va": str(valor_anterior) if valor_anterior else None,
               "vn": str(valor_novo) if valor_novo else None, "ts": _agora()})


def carregar_historico_orcamento(projeto: str) -> pd.DataFrame:
    """Retorna histórico de alterações de um projeto, mais recente primeiro."""
    with _engine().connect() as con:
        return pd.read_sql(text("""
            SELECT campo, valor_anterior, valor_novo, alterado_em
            FROM historico_orcamentos WHERE projeto = :p
            ORDER BY alterado_em DESC LIMIT 50
        """), con, params={"p": projeto})
```

**Auto-log in `salvar_orcamento`:** Antes de salvar, carregar o valor atual. Comparar `orcamento_previsto` e `status_projeto`. Se mudaram, chamar `registrar_historico_orcamento`.

**Display in 0_orcamento.py:** Após o formulário, nova seção colapsada "📋 Histórico de Alterações" (expander) com `st.dataframe(carregar_historico_orcamento(cc_selecionado))`.

- [ ] Testes em `tests/test_db_orcamentos.py`
- [ ] Commit: `feat: histórico de revisões de orçamento`

---

### Task 14: B5 — Comentário Geral por Projeto

**Files:**
- Modify: `dashboard_projetos/utils/db.py` — nova coluna + update `salvar_orcamento`
- Modify: `dashboard_projetos/pages/0_orcamento.py` — campo de texto

**Migration (in `migrar_db`):**
```python
with engine.begin() as con:
    try:
        con.execute(text("ALTER TABLE orcamentos_cronograma ADD COLUMN IF NOT EXISTS comentario_geral TEXT"))
    except Exception:
        pass
```

**Update `salvar_orcamento`:** Adicionar parâmetro `comentario_geral: str | None = None` e incluir no INSERT/UPDATE.

**Update `carregar_orcamento_projeto`:** Incluir `comentario_geral` no SELECT e retorno.

**Update `COLUNAS_DB_ORCAMENTOS`:** Adicionar `"comentario_geral"` à lista.

**Display in 0_orcamento.py:** No formulário principal, após a seção de status, adicionar:
```python
st.subheader("💬 Comentário Geral")
comentario_salvo = (dados.get("comentario_geral") or "") if dados else ""
v_comentario = st.text_area(
    "Comentário geral do projeto:",
    value=comentario_salvo,
    placeholder="Observações gerais, decisões estratégicas, contexto do projeto…",
    height=100,
    disabled=not _admin,
    help="Visível para todos os usuários. Editável apenas por administradores.",
)
```

Incluir `v_comentario` no `salvar_orcamento(...)` ao salvar.

- [ ] Testes em `tests/test_db_orcamentos.py`
- [ ] Commit: `feat: comentário geral por projeto`

---

### Task 15: C6 — Unificação Visual

**Files:**
- Modify: `dashboard_projetos/pages/2_dashboard.py`
- Modify: `dashboard_projetos/pages/3_projetos.py`
- Modify: `dashboard_projetos/pages/4_visao_executiva.py`
- Modify: `dashboard_projetos/pages/5_dashboard_executivo.py`

**Rules:**
1. Remover `st.divider()` consecutivos (≥ 2 seguidos) — manter apenas 1.
2. Padronizar cabeçalhos de seção: usar `st.subheader(...)` para nível 2, `st.markdown("#### ...")` apenas para nível 3 dentro de tabs/expanders.
3. Em `3_projetos.py` Tab Detalhamento: os `st.markdown("#### ...")` abaixo de cada seção do projeto (Burn de Custo, Cronograma, Horas, Evolução Mensal, Projeção) → manter como estão (são nível 3 correto dentro da aba).
4. Em `5_dashboard_executivo.py`: os `st.subheader(...)` dentro de `with tab_resumo:` etc. estão corretos — não alterar.
5. Remover `st.markdown("<br>", unsafe_allow_html=True)` isolados (usar `st.markdown("")` em vez de, ou remover).

**Do NOT:** Alterar lógica de negócio, queries, cálculos ou imports. Apenas limpeza visual.

- [ ] Commit: `style: unificação visual — dividers e hierarquia de headers`

---

## Nota: Itens Excluídos

- **A2** (consolidar navegação): pós-merge — requer todas as features prontas primeiro.
- **B4** (orçamento por categoria): requer UI de entrada de dados por categoria, fora de escopo desta fase.
- **B6** (edição em tabela): limitação do Streamlit para edição in-place com salvamento granular.
- **C1, C3, C4, C5, C7**: alta complexidade ou dependência externa — próxima fase.
