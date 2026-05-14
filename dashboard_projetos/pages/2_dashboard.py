import pages._pathfix
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

with st.sidebar:
    st.header("🔍 Filtros")
    projetos_all = sorted(df["projeto"].unique().tolist())
    projetos_sel = st.multiselect("Projetos", projetos_all, default=projetos_all)
    meses_all = sorted(df_custos["mes"].dropna().unique().tolist()) if "mes" in df_custos.columns else []
    meses_sel = st.multiselect("Mês de referência", meses_all, default=meses_all) if meses_all else []

df_f   = df[df["projeto"].isin(projetos_sel)]
df_c_f = df_custos[df_custos["projeto"].isin(projetos_sel)]
df_h_f = df_horas[df_horas["projeto"].isin(projetos_sel)]
if meses_sel and "mes" in df_c_f.columns:
    df_c_f = df_c_f[df_c_f["mes"].isin(meses_sel)]
if meses_sel and "mes" in df_h_f.columns:
    df_h_f = df_h_f[df_h_f["mes"].isin(meses_sel)]

st.subheader("Visão Geral")
k1, k2, k3, k4, k5 = st.columns(5)
total_custo   = df_f["valor_total"].sum()
total_orca    = df_f["orcamento"].sum()
total_horas   = df_f["horas_total"].sum()
custo_h_medio = total_custo / total_horas if total_horas > 0 else 0
pct_global    = total_custo / total_orca * 100 if total_orca > 0 else 0

k1.metric("💰 Custo Total",       formata_brl(total_custo))
k2.metric("📋 Orçamento Total",   formata_brl(total_orca))
k3.metric("⏱️ Horas Totais",      f"{total_horas:,.0f} h")
k4.metric("📐 Custo Médio/Hora",  formata_brl(custo_h_medio))
k5.metric("📊 % Orçamento Usado", f"{pct_global:.1f}%",
          delta=f"{pct_global - 80:.1f}pp vs meta 80%" if total_orca > 0 else None,
          delta_color="inverse")

st.divider()
col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(charts.grafico_custo_vs_orcamento(df_f), use_container_width=True)
with col2:
    st.plotly_chart(charts.grafico_horas_por_projeto(df_f), use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    st.plotly_chart(charts.grafico_custo_por_hora(df_f), use_container_width=True)
with col4:
    if not df_c_f.empty and "categoria" in df_c_f.columns:
        st.plotly_chart(charts.grafico_pizza_categorias(df_c_f), use_container_width=True)

if not df_c_f.empty and not df_h_f.empty:
    st.subheader("Evolução Mensal")
    st.plotly_chart(charts.grafico_evolucao_mensal(df_c_f, df_h_f), use_container_width=True)

st.divider()
st.subheader("Tabela Resumo por Projeto")
tabela = df_f[["projeto","valor_total","orcamento","saldo_orcamento",
               "horas_total","custo_por_hora","pct_orcamento","n_colaboradores","status"]].copy()
tabela.insert(0, "🚦", tabela["pct_orcamento"].apply(cor_status))
tabela.columns = ["🚦","Projeto","Custo (R$)","Orçamento (R$)","Saldo (R$)",
                  "Horas","R$/h","% Orçamento","Colaboradores","Status"]
st.dataframe(
    tabela.style.format({
        "Custo (R$)":     "R$ {:,.2f}",
        "Orçamento (R$)": "R$ {:,.2f}",
        "Saldo (R$)":     "R$ {:,.2f}",
        "Horas":          "{:.0f}",
        "R$/h":           "R$ {:.2f}",
        "% Orçamento":    "{:.1f}%",
    }).background_gradient(subset=["% Orçamento"], cmap="RdYlGn_r"),
    use_container_width=True, hide_index=True,
)
csv = tabela.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Exportar CSV", csv, "resumo_projetos.csv", "text/csv")
