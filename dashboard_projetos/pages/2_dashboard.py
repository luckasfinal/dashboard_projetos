import sys
from pathlib import Path
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from datetime import datetime
import streamlit as st
import pandas as pd
from utils.db import init_db
from utils.data_processor import agregar_tudo, formata_brl, cor_status
from utils import charts

init_db()

# ── CSS global ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* KPI cards */
div[data-testid="metric-container"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px 18px 10px;
}
div[data-testid="metric-container"] label { color: #64748b; font-size: 13px; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { font-size: 22px; font-weight: 700; }

/* Tabela zebrada */
div[data-testid="stDataFrame"] table tr:nth-child(even) td { background-color: #f8fafc; }

/* Sidebar compacta */
section[data-testid="stSidebar"] { min-width: 240px !important; max-width: 260px !important; }
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard Financeiro")

df_dashboard, df_custos_raw, df_horas_raw = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

# ── Opções de filtro ──────────────────────────────────────────────────────────
lista_projetos = sorted(df_dashboard["nome_projeto"].dropna().unique().tolist())
lista_anos     = sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist()) if "ano" in df_custos_raw.columns else []
lista_meses    = sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist()) if "mes" in df_custos_raw.columns else []

if "filtro_projetos" not in st.session_state: st.session_state["filtro_projetos"] = lista_projetos
if "filtro_anos"     not in st.session_state: st.session_state["filtro_anos"]     = lista_anos
if "filtro_meses"    not in st.session_state: st.session_state["filtro_meses"]    = lista_meses

st.session_state["filtro_projetos"] = [p for p in st.session_state["filtro_projetos"] if p in lista_projetos]
st.session_state["filtro_anos"]     = [a for a in st.session_state["filtro_anos"]     if a in lista_anos]
st.session_state["filtro_meses"]    = [m for m in st.session_state["filtro_meses"]    if m in lista_meses]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filtros")
    projetos_selecionados = st.multiselect("Projetos:", options=lista_projetos,
        default=st.session_state["filtro_projetos"], key="filtro_projetos")
    anos_selecionados = st.multiselect("Ano:", options=lista_anos,
        default=st.session_state["filtro_anos"], key="filtro_anos")
    meses_selecionados = st.multiselect("Mês:", options=lista_meses,
        default=st.session_state["filtro_meses"], key="filtro_meses")
    if st.button("🔄 Limpar filtros", use_container_width=True):
        st.session_state["filtro_projetos"] = lista_projetos
        st.session_state["filtro_anos"]     = lista_anos
        st.session_state["filtro_meses"]    = lista_meses
        st.rerun()

# ── Filtros ───────────────────────────────────────────────────────────────────
df_f = df_dashboard.copy()
if projetos_selecionados:
    df_f = df_f[df_f["nome_projeto"].isin(projetos_selecionados)]
if anos_selecionados and "ano" in df_custos_raw.columns:
    cc_anos = df_custos_raw[df_custos_raw["ano"].astype(str).isin(anos_selecionados)]["centro_de_custo"].unique()
    df_f = df_f[df_f["projeto"].isin(cc_anos)]
if meses_selecionados and "mes" in df_custos_raw.columns:
    cc_meses = df_custos_raw[df_custos_raw["mes"].astype(str).isin(meses_selecionados)]["centro_de_custo"].unique()
    df_f = df_f[df_f["projeto"].isin(cc_meses)]

df_c_f  = df_custos_raw[df_custos_raw["centro_de_custo"].isin(df_f["projeto"])] if not df_custos_raw.empty else df_custos_raw
df_h_f  = df_horas_raw[df_horas_raw["c_custo"].isin(df_f["projeto"])]           if not df_horas_raw.empty else df_horas_raw
mes_col = "mes_ref" if "mes_ref" in df_c_f.columns else None

if df_f.empty:
    st.info("Nenhum projeto encontrado para os filtros selecionados.")
    st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────
total_custo   = df_f["valor_total"].sum()
total_horas   = df_f["horas_total"].sum()
custo_h_medio = total_custo / total_horas if total_horas > 0 else 0
n_projetos    = len(df_f)
tem_orc       = (df_f.get("orcamento", pd.Series([0])) > 0).any()
total_orc     = df_f["orcamento"].sum() if tem_orc else 0
saldo_total   = total_orc - total_custo if tem_orc else None

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("📁 Projetos",          str(n_projetos))
k2.metric("💰 Realizado Total",   formata_brl(total_custo))
k3.metric("🎯 Orçamento Total",   formata_brl(total_orc) if tem_orc else "N/D")
k4.metric("💹 Saldo Consolidado", formata_brl(saldo_total) if saldo_total is not None else "N/D",
          delta=f"{(total_custo/total_orc*100):.1f}% consumido" if tem_orc and total_orc > 0 else None,
          delta_color="inverse")
k5.metric("⏱️ Horas Totais",      f"{total_horas:,.0f} h")

st.divider()

# ── Linha 1 de gráficos: Realizado vs Orçamento + Pizza contas ────────────────
col1, col2 = st.columns([3, 2])
with col1:
    if tem_orc:
        st.plotly_chart(charts.grafico_custo_vs_orcamento(df_f), use_container_width=True)
    else:
        st.plotly_chart(charts.grafico_realizado_por_projeto(df_f), use_container_width=True)
with col2:
    if not df_c_f.empty and "conta" in df_c_f.columns:
        st.plotly_chart(charts.grafico_pizza_conta(df_c_f), use_container_width=True)

# ── Linha 2: Horas + Custo/h ──────────────────────────────────────────────────
col3, col4 = st.columns(2)
with col3:
    st.plotly_chart(charts.grafico_horas_por_projeto(df_f), use_container_width=True)
with col4:
    st.plotly_chart(charts.grafico_custo_por_hora(df_f), use_container_width=True)

# ── Evolução mensal ───────────────────────────────────────────────────────────
if not df_c_f.empty and mes_col:
    st.subheader("📅 Evolução Mensal")
    st.plotly_chart(charts.grafico_evolucao_mensal(df_c_f, df_h_f, mes_col), use_container_width=True)

st.divider()

# ── Tabela resumo com status visual ──────────────────────────────────────────
st.subheader("📋 Resumo por Projeto")

cols_disp = ["projeto", "nome_projeto", "valor_total", "horas_total", "custo_por_hora"]
if tem_orc:
    cols_disp += ["orcamento", "saldo_orcamento", "pct_orcamento"]
for c in ["filial", "area", "segmento"]:
    if c in df_f.columns and df_f[c].astype(str).replace("0","").str.strip().any():
        cols_disp.append(c)

tabela = df_f[cols_disp].copy()
if "pct_orcamento" in tabela.columns:
    tabela.insert(0, "🚦", tabela["pct_orcamento"].apply(cor_status))

tabela.rename(columns={
    "projeto":         "CC",
    "nome_projeto":    "Projeto",
    "valor_total":     "Realizado (R$)",
    "horas_total":     "Horas",
    "custo_por_hora":  "R$/h",
    "orcamento":       "Orçamento (R$)",
    "saldo_orcamento": "Saldo (R$)",
    "pct_orcamento":   "% Orç.",
    "filial": "Filial", "area": "Área", "segmento": "Segmento",
}, inplace=True)

fmt = {"Realizado (R$)": "R$ {:,.2f}", "Horas": "{:.0f}", "R$/h": "R$ {:.2f}"}
if "Orçamento (R$)" in tabela.columns:
    fmt |= {"Orçamento (R$)": "R$ {:,.2f}", "Saldo (R$)": "R$ {:,.2f}", "% Orç.": "{:.1f}%"}

def _cor_pct(val):
    try:
        v = float(str(val).replace("%","").replace(",",".").strip())
    except Exception:
        return ""
    if v > 100: return "background-color:#c0392b;color:white;font-weight:bold"
    if v >= 90: return "background-color:#ffd6d6;color:#7a0000"
    if v >= 70: return "background-color:#fff3cd;color:#664d00"
    return "background-color:#d4edda;color:#155724"

styler = tabela.style.format(fmt)
if "% Orç." in tabela.columns:
    styler = styler.applymap(_cor_pct, subset=["% Orç."])

st.dataframe(styler, use_container_width=True, hide_index=True)

col_dl, _ = st.columns([1, 4])
csv = tabela.to_csv(index=False).encode("utf-8")
col_dl.download_button("⬇️ Exportar CSV", csv, "resumo_projetos.csv", "text/csv")
