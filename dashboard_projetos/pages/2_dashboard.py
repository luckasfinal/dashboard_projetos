import sys
from pathlib import Path
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from utils.db import init_db
from utils.data_processor import agregar_tudo, formata_brl, cor_status
from utils import charts

init_db()
st.title("📊 Dashboard Financeiro")

df, df_custos, df_horas = agregar_tudo()

if df.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filtros")
    projetos_all = sorted(df["projeto"].unique().tolist())
    projetos_sel = st.multiselect("Centro de Custo / Projeto", projetos_all, default=projetos_all)

    # Filtro por mês (usa mes_ref gerado no processor)
    meses_all = []
    if "mes_ref" in df_custos.columns:
        meses_all = sorted(df_custos["mes_ref"].dropna().unique().tolist())
    elif "mes" in df_custos.columns:
        meses_all = sorted(df_custos["mes"].dropna().unique().tolist())
    meses_sel = st.multiselect("Mês de referência", meses_all, default=meses_all) if meses_all else []

    # Filtro por área
    if "area" in df_custos.columns:
        areas_all = sorted(df_custos["area"].dropna().unique().tolist())
        areas_sel = st.multiselect("Área", areas_all, default=areas_all)
    else:
        areas_sel = []

    # Filtro por filial
    if "filial" in df_custos.columns:
        filiais_all = sorted(df_custos["filial"].dropna().unique().tolist())
        filiais_sel = st.multiselect("Filial", filiais_all, default=filiais_all)
    else:
        filiais_sel = []

df_f   = df[df["projeto"].isin(projetos_sel)]
df_c_f = df_custos[df_custos["centro_de_custo"].isin(projetos_sel)] if "centro_de_custo" in df_custos.columns else df_custos
df_h_f = df_horas[df_horas["c_custo"].isin(projetos_sel)] if "c_custo" in df_horas.columns else df_horas

mes_col = "mes_ref" if "mes_ref" in df_c_f.columns else ("mes" if "mes" in df_c_f.columns else None)
if meses_sel and mes_col:
    df_c_f = df_c_f[df_c_f[mes_col].isin(meses_sel)]
if meses_sel and "mes_ref" in df_h_f.columns:
    df_h_f = df_h_f[df_h_f["mes_ref"].isin(meses_sel)]
if areas_sel and "area" in df_c_f.columns:
    df_c_f = df_c_f[df_c_f["area"].isin(areas_sel)]
if filiais_sel and "filial" in df_c_f.columns:
    df_c_f = df_c_f[df_c_f["filial"].isin(filiais_sel)]

# ── KPIs ─────────────────────────────────────────────────────────────────────
st.subheader("Visão Geral")
k1, k2, k3, k4 = st.columns(4)

total_custo   = df_f["valor_total"].sum()
total_horas   = df_f["horas_total"].sum()
custo_h_medio = total_custo / total_horas if total_horas > 0 else 0
n_projetos    = len(df_f)

k1.metric("💰 Realizado Total",    formata_brl(total_custo))
k2.metric("⏱️ Horas Totais",       f"{total_horas:,.0f} h")
k3.metric("📐 Custo Médio/Hora",   formata_brl(custo_h_medio))
k4.metric("📁 Projetos (CC)",      str(n_projetos))

st.divider()

# ── Gráficos ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(charts.grafico_realizado_por_projeto(df_f), width="stretch")
with col2:
    st.plotly_chart(charts.grafico_horas_por_projeto(df_f), width="stretch")

col3, col4 = st.columns(2)
with col3:
    st.plotly_chart(charts.grafico_custo_por_hora(df_f), width="stretch")
with col4:
    if not df_c_f.empty and "conta" in df_c_f.columns:
        st.plotly_chart(charts.grafico_pizza_conta(df_c_f), width="stretch")

if not df_c_f.empty and mes_col:
    st.subheader("Evolução Mensal")
    st.plotly_chart(charts.grafico_evolucao_mensal(df_c_f, df_h_f, mes_col), width="stretch")

st.divider()

# ── Tabela resumo ─────────────────────────────────────────────────────────────
st.subheader("Tabela Resumo por Centro de Custo")

cols_disp = ["projeto", "valor_total", "horas_total", "custo_por_hora"]
for c in ["filial", "area", "tipo_projeto", "segmento"]:
    if c in df_f.columns:
        cols_disp.append(c)

tabela = df_f[cols_disp].copy()

rename_map = {
    "projeto":       "Centro de Custo",
    "valor_total":   "Realizado (R$)",
    "horas_total":   "Horas",
    "custo_por_hora":"R$/h",
    "filial":        "Filial",
    "area":          "Área",
    "tipo_projeto":  "Tipo Projeto",
    "segmento":      "Segmento",
}
tabela.rename(columns=rename_map, inplace=True)

fmt = {
    "Realizado (R$)": "R$ {:,.2f}",
    "Horas":          "{:.0f}",
    "R$/h":           "R$ {:.2f}",
}

def colorir_realizado(val):
    return ""  # sem dependência externa

st.dataframe(
    tabela.style.format(fmt),
    width="stretch",
    hide_index=True,
)

csv = tabela.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Exportar CSV", csv, "resumo_projetos.csv", "text/csv")
