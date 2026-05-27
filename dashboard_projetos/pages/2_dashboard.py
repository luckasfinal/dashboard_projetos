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

# ── CSS Seguro — Compatibilidade Light/Dark Mode ─────────────────────────────
st.markdown("""
<style>
/* Cards de KPI */
div[data-testid="metric-container"] {
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 10px;
    padding: 12px 14px 8px;
    min-width: 0;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: clamp(14px, 2vw, 20px) !important;
    font-weight: 700;
    white-space: nowrap;
    overflow: visible !important;
    text-overflow: unset !important;
}
div[data-testid="metric-container"] label {
    font-size: 12px;
    opacity: 0.7;
}
/* Sidebar Customizada */
section[data-testid="stSidebar"] { min-width: 240px !important; max-width: 260px !important; }
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard Financeiro")

df_dashboard, df_custos_raw, df_horas_raw = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

# ── Gerenciamento Avançado e Seguro de Filtros (Sem colisões de chaves) ──────
lista_projetos = sorted(df_dashboard["nome_projeto"].dropna().unique().tolist())
lista_anos     = sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist()) if "ano" in df_custos_raw.columns else []
lista_meses    = sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist()) if "mes" in df_custos_raw.columns else []

if "sel_projetos" not in st.session_state: st.session_state["sel_projetos"] = lista_projetos
if "sel_anos"     not in st.session_state: st.session_state["sel_anos"]     = lista_anos
if "sel_meses"    not in st.session_state: st.session_state["sel_meses"]    = lista_meses

# Higienização dos estados salvos contra mudanças estruturais do banco
default_projetos = [p for p in st.session_state["sel_projetos"] if p in lista_projetos]
default_anos     = [a for a in st.session_state["sel_anos"] if a in lista_anos]
default_meses    = [m for m in st.session_state["sel_meses"] if m in lista_meses]

if not default_projetos: default_projetos = lista_projetos
if not default_anos: default_anos = lista_anos
if not default_meses: default_meses = lista_meses

with st.sidebar:
    st.header("🔍 Filtros")
    projetos_selecionados = st.multiselect("Projetos:", options=lista_projetos, default=default_projetos)
    anos_selecionados     = st.multiselect("Ano:", options=lista_anos, default=default_anos)
    meses_selecionados    = st.multiselect("Mês:", options=lista_meses, default=default_meses)
    
    if st.button("🔄 Limpar filtros", use_container_width=True):
        st.session_state["sel_projetos"] = lista_projetos
        st.session_state["sel_anos"]     = lista_anos
        st.session_state["sel_meses"]    = lista_meses
        st.rerun()

# Atualiza persistência de estado para navegação entre páginas
st.session_state["sel_projetos"] = projetos_selecionados
st.session_state["sel_anos"]     = anos_selecionados
st.session_state["sel_meses"]    = meses_selecionados

# ── Aplicação Concreta dos Filtros ───────────────────────────────────────────
df_f = df_dashboard.copy()
if projetos_selecionados:
    df_f = df_f[df_f["nome_projeto"].isin(projetos_selecionados)]
if anos_selecionados and "ano" in df_custos_raw.columns:
    cc_anos = df_custos_raw[df_custos_raw["ano"].astype(str).isin(anos_selecionados)]["centro_de_custo"].unique()
    df_f = df_f[df_f["projeto"].isin(cc_anos)]
if meses_selecionados and "mes" in df_custos_raw.columns:
    cc_meses = df_custos_raw[df_custos_raw["mes"].astype(str).isin(meses_selecionados)]["centro_de_custo"].unique()
    df_f = df_f[df_f["projeto"].isin(cc_meses)]

if df_f.empty:
    st.info("💡 Nenhum projeto corresponde aos filtros selecionados na barra lateral.")
    st.stop()

df_c_f  = df_custos_raw[df_custos_raw["centro_de_custo"].isin(df_f["projeto"])] if not df_custos_raw.empty else df_custos_raw
df_h_f  = df_horas_raw[df_horas_raw["c_custo"].isin(df_f["projeto"])]           if not df_horas_raw.empty else df_horas_raw
mes_col = "mes_ref" if "mes_ref" in df_c_f.columns else None

# ── Métricas e KPIs Financeiros ───────────────────────────────────────────────
total_custo   = df_f["valor_total"].sum()
total_horas   = df_f["horas_total"].sum()
custo_h_medio = total_custo / total_horas if total_horas > 0 else 0
n_projetos    = len(df_f)
tem_orc       = (df_f.get("orcamento", pd.Series([0])) > 0).any()
total_orc     = df_f["orcamento"].sum() if tem_orc else 0
saldo_total   = total_orc - total_custo  if tem_orc else None
pct_consumido = (total_custo / total_orc * 100) if tem_orc and total_orc > 0 else None

r1c1, r1c2, r1c3 = st.columns(3)
r1c1.metric("📁 Projetos ativos",  str(n_projetos))
r1c2.metric("💰 Realizado Total",  formata_brl(total_custo))
r1c3.metric("🎯 Orçamento Total",  formata_brl(total_orc) if tem_orc else "Não cadastrado")

r2c1, r2c2, r2c3 = st.columns(3)
r2c1.metric(
    "💹 Saldo Consolidado",
    formata_brl(saldo_total) if saldo_total is not None else "N/D",
    delta=f"{pct_consumido:.1f}% consumido" if pct_consumido else None,
    delta_color="inverse",
)
r2c2.metric("⏱️ Horas Totais",      f"{total_horas:,.0f} h")
r2c3.metric("📐 Custo Médio/Hora",  formata_brl(custo_h_medio))

st.divider()

# ── Renderização Adaptativa de Gráficos ───────────────────────────────────────
col1, col2 = st.columns([3, 2])
with col1:
    if tem_orc:
        st.plotly_chart(charts.grafico_custo_vs_orcamento(df_f), use_container_width=True, theme="streamlit")
    else:
        st.plotly_chart(charts.grafico_realizado_por_projeto(df_f), use_container_width=True, theme="streamlit")
with col2:
    if not df_c_f.empty and "conta" in df_c_f.columns:
        st.plotly_chart(charts.grafico_pizza_conta(df_c_f), use_container_width=True, theme="streamlit")

col3, col4 = st.columns(2)
with col3:
    st.plotly_chart(charts.grafico_horas_por_projeto(df_f), use_container_width=True, theme="streamlit")
with col4:
    st.plotly_chart(charts.grafico_custo_por_hora(df_f), use_container_width=True, theme="streamlit")

if not df_c_f.empty and mes_col:
    st.subheader("📅 Evolução Mensal")
    st.plotly_chart(charts.grafico_evolucao_mensal(df_c_f, df_h_f, mes_col), use_container_width=True, theme="streamlit")

st.divider()

# ── Tabela Customizada de Alta Legibilidade ───────────────────────────────────
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
    if v > 100: return "background-color:#dc2626;color:white;font-weight:bold"
    if v >= 90: return "background-color:#ea580c;color:white;font-weight:bold"
    if v >= 70: return "background-color:#eab308;color:black;font-weight:bold"
    return "background-color:#16a34a;color:white;font-weight:bold"

styler = tabela.style.format(fmt)
if "% Orç." in tabela.columns:
    styler = styler.map(_cor_pct, subset=["% Orç."])

st.dataframe(styler, use_container_width=True, hide_index=True)

col_dl, _ = st.columns([1, 4])
csv = tabela.to_csv(index=False).encode("utf-8")
col_dl.download_button("⬇️ Exportar CSV", csv, "resumo_projetos.csv", "text/csv")
