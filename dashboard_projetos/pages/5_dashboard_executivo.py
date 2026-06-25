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
total_m     = len(df_marcos)
atrasados_m = int((df_marcos["status_marco"] == "Atrasado").sum())
pct_atr     = atrasados_m / total_m * 100 if total_m > 0 else 0
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
