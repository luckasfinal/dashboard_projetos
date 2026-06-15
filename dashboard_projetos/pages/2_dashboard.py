import sys
from pathlib import Path
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from utils.db import init_db
from utils.data_processor import (
    agregar_tudo, formata_brl, formata_brl_curto, cor_status, cor_status_projeto,
    render_selo_dados, aviso_truncamento, detectar_excecoes,
    status_ativos, anos_default,
)
from utils import charts

init_db()

st.markdown("""
<style>
div[data-testid="metric-container"] {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 10px;
    padding: 12px 14px 8px;
    min-width: 0;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: clamp(14px, 2vw, 20px) !important;
    font-weight: 700;
    white-space: nowrap;
    overflow: visible !important;
}
div[data-testid="metric-container"] label { font-size: 12px; opacity: .7; }
section[data-testid="stSidebar"] { min-width: 240px !important; max-width: 260px !important; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Dashboard Financeiro")
st.caption("Foco em **custos e orçamento**. Para prazos, status e cronograma, veja **Andamento dos Projetos**.")

df_dashboard, df_custos_raw, df_horas_raw = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

# ── Filtros persistentes ──────────────────────────────────────────────────────
lista_projetos = sorted(df_dashboard["nome_projeto"].dropna().unique().tolist())
lista_anos     = sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist()) if "ano" in df_custos_raw.columns else []
lista_meses    = sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist()) if "mes" in df_custos_raw.columns else []
lista_status   = sorted(df_dashboard["status_projeto"].dropna().unique().tolist()) if "status_projeto" in df_dashboard.columns else []

if "filtro_projetos" not in st.session_state: st.session_state["filtro_projetos"] = lista_projetos
if "filtro_anos"     not in st.session_state: st.session_state["filtro_anos"]     = anos_default(lista_anos)
if "filtro_meses"    not in st.session_state: st.session_state["filtro_meses"]    = lista_meses
if "filtro_status"   not in st.session_state: st.session_state["filtro_status"]   = status_ativos(lista_status)

st.session_state["filtro_projetos"] = [p for p in st.session_state["filtro_projetos"] if p in lista_projetos]
st.session_state["filtro_anos"]     = [a for a in st.session_state["filtro_anos"]     if a in lista_anos]
st.session_state["filtro_meses"]    = [m for m in st.session_state["filtro_meses"]    if m in lista_meses]
st.session_state["filtro_status"]   = [s for s in st.session_state["filtro_status"]   if s in lista_status]

with st.sidebar:
    st.header("🔍 Filtros")
    projetos_selecionados = st.multiselect("Projetos:", options=lista_projetos,
        default=st.session_state["filtro_projetos"], key="filtro_projetos")
    anos_selecionados = st.multiselect("Ano:", options=lista_anos,
        default=st.session_state["filtro_anos"], key="filtro_anos")
    meses_selecionados = st.multiselect("Mês:", options=lista_meses,
        default=st.session_state["filtro_meses"], key="filtro_meses")
    status_selecionados = st.multiselect("Status do Projeto:", options=lista_status,
        default=st.session_state["filtro_status"], key="filtro_status")
    if st.button("🔄 Limpar filtros", use_container_width=True):
        st.session_state["filtro_projetos"] = lista_projetos
        st.session_state["filtro_anos"]     = lista_anos
        st.session_state["filtro_meses"]    = lista_meses
        st.session_state["filtro_status"]   = lista_status
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
if status_selecionados and "status_projeto" in df_f.columns:
    df_f = df_f[df_f["status_projeto"].isin(status_selecionados)]

df_c_f  = df_custos_raw[df_custos_raw["centro_de_custo"].isin(df_f["projeto"])] if not df_custos_raw.empty else df_custos_raw
df_h_f  = df_horas_raw[df_horas_raw["c_custo"].isin(df_f["projeto"])]           if not df_horas_raw.empty else df_horas_raw
mes_col = "mes_ref" if "mes_ref" in df_c_f.columns else None

if df_f.empty:
    st.info("Nenhum projeto encontrado para os filtros selecionados.")
    st.stop()

# ── Selo de confiança: atualização + completude (recorte filtrado) ────────────
render_selo_dados(df_f)

# ── KPIs ──────────────────────────────────────────────────────────────────────
# Linha 1: Orçamento Total | Realizado Total | Saldo Consolidado
# Linha 2: Projetos Ativos | Horas Totais | Custo Médio/Hora
total_custo   = df_f["valor_total"].sum()
total_horas   = df_f["horas_total"].sum()
custo_h_medio = total_custo / total_horas if total_horas > 0 else 0
n_projetos    = len(df_f)
tem_orc       = (df_f.get("orcamento", pd.Series([0])) > 0).any()
total_orc     = df_f["orcamento"].sum() if tem_orc else 0
saldo_total   = total_orc - total_custo  if tem_orc else None
pct_consumido = (total_custo / total_orc * 100) if tem_orc and total_orc > 0 else None

# Exceções para enriquecer o KPI de Saldo (Fase 2.2)
exc = detectar_excecoes(df_f)

# Linha 1 — valores abreviados; valor cheio no tooltip (help)
l1c1, l1c2, l1c3 = st.columns(3)
l1c1.metric(
    "🎯 Orçamento Total",
    formata_brl_curto(total_orc) if tem_orc else "Não cadastrado",
    help=f"Valor exato: {formata_brl(total_orc)}" if tem_orc else None,
)
l1c2.metric(
    "💰 Realizado Total",
    formata_brl_curto(total_custo),
    help=f"Valor exato: {formata_brl(total_custo)}",
)

if exc["n_estouro"] > 0:
    saldo_delta = f"🚨 {exc['n_estouro']} em estouro · +{formata_brl_curto(exc['excedente_total'])}"
    saldo_help = (
        f"Saldo exato: {formata_brl(saldo_total) if saldo_total is not None else 'N/D'}\n\n"
        f"{exc['n_estouro']} projeto(s) acima do orçamento, "
        f"somando {formata_brl(exc['excedente_total'])} de excedente."
    )
else:
    saldo_delta = f"{pct_consumido:.1f}% consumido" if pct_consumido else None
    saldo_help = f"Valor exato: {formata_brl(saldo_total)}" if saldo_total is not None else None

l1c3.metric(
    "💹 Saldo Consolidado",
    formata_brl_curto(saldo_total) if saldo_total is not None else "N/D",
    delta=saldo_delta,
    delta_color="inverse",
    help=saldo_help,
)

# Linha 2
l2c1, l2c2, l2c3 = st.columns(3)
l2c1.metric("📁 Projetos Ativos",   str(n_projetos))
l2c2.metric("⏱️ Horas Totais",      f"{total_horas:,.0f} h")
l2c3.metric(
    "📐 Custo Médio/Hora",
    formata_brl(custo_h_medio),  # valores por hora são pequenos — mantém cheio
)

st.divider()

# ── Gráficos financeiros — um por linha ───────────────────────────────────────
n_proj_graf = len(df_f)
if tem_orc:
    # grafico_custo_vs_orcamento usa todos os projetos — não trunca
    st.plotly_chart(charts.grafico_custo_vs_orcamento(df_f), use_container_width=True)
else:
    st.plotly_chart(charts.grafico_realizado_por_projeto(df_f), use_container_width=True)
    aviso_truncamento(n_proj_graf)

st.plotly_chart(charts.grafico_custo_por_hora(df_f), use_container_width=True)
aviso_truncamento(len(df_f[df_f["custo_por_hora"] > 0]))

if not df_c_f.empty and "conta" in df_c_f.columns:
    st.plotly_chart(charts.grafico_pizza_conta(df_c_f), use_container_width=True)

if not df_c_f.empty and mes_col:
    st.plotly_chart(charts.grafico_evolucao_mensal(df_c_f, df_h_f, mes_col), use_container_width=True)

st.divider()

# ── Tabela resumo ─────────────────────────────────────────────────────────────
st.subheader("📋 Resumo por Projeto")

cols_disp = ["projeto", "nome_projeto", "valor_total", "horas_total", "custo_por_hora"]
if tem_orc:
    cols_disp += ["orcamento", "saldo_orcamento", "pct_orcamento"]
for c in ["filial", "area", "segmento"]:
    if c in df_f.columns and df_f[c].astype(str).replace("0", "").str.strip().any():
        cols_disp.append(c)

cols_disp = [c for c in cols_disp if c in df_f.columns]
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
        v = float(str(val).replace("%", "").replace(",", ".").strip())
    except Exception:
        return ""
    if v > 100: return "background-color:#7f1d1d;color:#fca5a5;font-weight:bold"
    if v >= 90: return "background-color:#7c2d12;color:#fdba74"
    if v >= 70: return "background-color:#713f12;color:#fde68a"
    return "background-color:#14532d;color:#86efac"

styler = tabela.style.format(fmt)
if "% Orç." in tabela.columns:
    styler = styler.map(_cor_pct, subset=["% Orç."])

st.dataframe(styler, use_container_width=True, hide_index=True)

col_dl, _ = st.columns([1, 4])
csv = tabela.to_csv(index=False).encode("utf-8")
col_dl.download_button("⬇️ Exportar CSV", csv, "resumo_projetos.csv", "text/csv")
