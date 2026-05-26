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

# 1. Carrega os dados processados e consolidados do banco
df_dashboard, df_custos_raw, df_horas_raw = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

# ── Sidebar (Filtros em Linhas e Multi-seleção) ───────────────────────────────
with st.sidebar:
    st.header("🔍 Filtros")
    
    # Filtro 1: Projeto (Mudado para multiselect em uma linha própria)
    lista_projetos = sorted(df_dashboard["nome_projeto"].dropna().unique().tolist())
    projetos_selecionados = st.multiselect(
        "Selecione os Projetos:", 
        options=lista_projetos,
        default=lista_projetos # Vazio por padrão significa que não está filtrando nada (mostra tudo)
    )
    
    # Filtro 2: Ano (Em uma linha própria)
    if "ano" in df_custos_raw.columns:
        lista_anos = sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist())
    else:
        lista_anos = []
    anos_selecionados = st.multiselect(
        "Selecione os Anos:", 
        options=lista_anos,
        default=lista_anos
    )
    
    # Filtro 3: Mês (Em uma linha própria)
    if "mes" in df_custos_raw.columns:
        lista_meses = sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist())
    else:
        lista_meses = []
    meses_selecionados = st.multiselect(
        "Selecione os Meses:", 
        options=lista_meses,
        default=lista_meses
    )

# ── 2. Aplicação dos filtros Multi-seleção (Fora da Sidebar) ──────────────────
df_filtrado = df_dashboard.copy()

# Aplicando filtro multi-seleção de projeto
if projetos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["nome_projeto"].isin(projetos_selecionados)]
    
# Aplicando filtro multi-seleção de ano
if anos_selecionados and "ano" in df_custos_raw.columns:
    # Filtra na base bruta quais centros de custo tiveram movimentação nos anos escolhidos
    projetos_nos_anos = df_custos_raw[df_custos_raw["ano"].astype(str).isin(anos_selecionados)]["centro_de_custo"].unique()
    df_filtrado = df_filtrado[df_filtrado["projeto"].isin(projetos_nos_anos)]
    
# Aplicando filtro multi-seleção de mês
if meses_selecionados and "mes" in df_custos_raw.columns:
    # Filtra na base bruta quais centros de custo tiveram movimentação nos meses escolhidos
    projetos_nos_meses = df_custos_raw[df_custos_raw["mes"].astype(str).isin(meses_selecionados)]["centro_de_custo"].unique()
    df_filtrado = df_filtrado[df_filtrado["projeto"].isin(projetos_nos_meses)]

# Mapeia os DataFrames brutos filtrados para manter a compatibilidade com seus gráficos originais
df_f = df_filtrado
df_c_f = df_custos_raw[df_custos_raw["centro_de_custo"].isin(df_f["projeto"])] if not df_custos_raw.empty else df_custos_raw
df_h_f = df_horas_raw[df_horas_raw["c_custo"].isin(df_f["projeto"])] if not df_horas_raw.empty else df_horas_raw
mes_col = "mes_ref" if "mes_ref" in df_c_f.columns else None

# ── 3. Tabela Visual com Nome do Projeto (Gasto Não-Nulo) ──────────────────────
if not df_filtrado.empty:
    df_visual = df_filtrado[[
        "projeto", 
        "nome_projeto", 
        "valor_total", 
        "horas_total", 
        "custo_por_hora"
    ]].rename(columns={
        "projeto": "Centro de Custo",
        "nome_projeto": "Nome do Projeto",
        "valor_total": "Realizado (R$)",
        "horas_total": "Horas Acumuladas",
        "custo_por_hora": "R$/h"
    })

    st.subheader("Análise de Projetos com Gastos Ativos")
    st.dataframe(df_visual, use_container_width=True)
else:
    st.info("Nenhum projeto encontrado para os filtros selecionados.")

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

csv = tabela.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Exportar CSV", csv, "resumo_projetos.csv", "text/csv")
