import sys
from pathlib import Path
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from utils.db import init_db
from utils.data_processor import agregar_tudo, formata_brl, cor_status
from utils import charts
# Importa a função que atualizamos no data_processor
from data_processor import agregar_tudo

init_db()
st.title("📊 Dashboard Financeiro")

df_dashboard, df_custos_raw, df_horas_raw = agregar_tudo()

if df_dashboard.empty
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filtros")
    # Criamos 3 colunas para colocar os filtros lado a lado na horizontal
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filtro de Projeto
        lista_projetos = ["Todos"] + sorted(df_dashboard["nome_projeto"].dropna().unique().tolist())
        projeto_selecionado = st.selectbox("Selecione o Projeto:", options=lista_projetos)
        
    with col2:
        # Filtro de Ano
        # Tenta buscar os anos da base de custos, caso não existam, deixa 'Todos'
        if "ano" in df_custos_raw.columns:
            lista_anos = ["Todos"] + sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist())
        else:
            lista_anos = ["Todos"]
        ano_selecionado = st.selectbox("Selecione o Ano:", options=lista_anos)
        
    with col3:
        # Filtro de Mês
        if "mes" in df_custos_raw.columns:
            lista_meses = ["Todos"] + sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist())
        else:
            lista_meses = ["Todos"]
        mes_selecionado = st.selectbox("Selecione o Mês:", options=lista_meses)

    # 2. Aplicação em cascata dos filtros no DataFrame principal
    df_filtrado = df_dashboard.copy()
    
    # Aplicando o filtro de projeto
    if proyecto_selecionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["nome_projeto"] == proyecto_selecionado]
        
    # Aplicando o filtro de ano (utilizando as referências temporárias cruzadas se necessário)
    if ano_selecionado != "Todos" and "ano" in df_custos_raw.columns:
        # Descobre quais projetos têm movimentação no ano selecionado
        projetos_no_ano = df_custos_raw[df_custos_raw["ano"].astype(str) == ano_selecionado]["centro_de_custo"].unique()
        df_filtrado = df_filtrado[df_filtrado["projeto"].isin(projetos_no_ano)]
        
    # Aplicando o filtro de mês
    if mes_selecionado != "Todos" and "mes" in df_custos_raw.columns:
        # Descobre quais projetos têm movimentação no mês selecionado
        projetos_no_mes = df_custos_raw[df_custos_raw["mes"].astype(str) == mes_selecionado]["centro_de_custo"].unique()
        df_filtrado = df_filtrado[df_filtrado["projeto"].isin(projetos_no_mes)]


    # 3. Prepara a tabela visual formatada usando o DataFrame filtrado resultante
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
    
    # 4. Exibe a tabela final na tela
    st.dataframe(df_visual, use_container_width=True)

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

# 1. Busca os dados consolidados e já filtrados (apenas maiores que zero)
df_dashboard, _, _ = agregar_tudo()

# 2. Verifica se o DataFrame não está vazio para evitar erros na tela
if not df_dashboard.empty:
    
    # 3. Filtra e reordena as colunas para o usuário, incluindo o novo 'nome_projeto'
    df_visual = df_dashboard[[
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
    
    # 4. Exibe a tabela formatada ocupando a largura total da tela
    st.dataframe(df_visual, use_container_width=True)

else:
    st.info("Nenhum projeto com gasto não-nulo encontrado no momento.")

csv = tabela.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Exportar CSV", csv, "resumo_projetos.csv", "text/csv")
