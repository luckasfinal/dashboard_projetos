import sys
from pathlib import Path
import sqlite3
from datetime import datetime

_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from utils.db import init_db
from utils.data_processor import agregar_tudo

init_db()

st.set_page_config(page_title="Gestão de Orçamentos e Prazos", page_icon="📋", layout="wide")
st.title("📋 Planejamento de Orçamentos e Prazos")
st.markdown("Insira ou atualize o orçamento e o cronograma de marcos (Milestones) dos projetos.")

# 1. Carrega os projetos existentes na base de dados para o usuário selecionar
df_dashboard, _, _ = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum projeto encontrado no banco de dados. Importe as planilhas primeiro na página de Upload.")
    st.stop()

# Lista de Centros de Custo disponíveis cruzando Código + Nome do Projeto
lista_cc = sorted(df_dashboard["projeto"].unique().tolist())
mapeamento_nomes = dict(zip(df_dashboard["projeto"], df_dashboard["nome_projeto"]))

cc_selecionado = st.selectbox(
    "Selecione o Centro de Custo (CC) do Projeto:",
    options=lista_cc,
    format_func=lambda x: f"{x} - {mapeamento_nomes.get(x, 'Sem Nome')}"
)

# Conexão com o banco para buscar dados já salvos anteriormente (se existirem)
conn = sqlite3.connect("dados_projetos.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM orcamentos_cronograma WHERE projeto = ?", (cc_selecionado,))
dados_existentes = cursor.fetchone()
conn.close()

# Função auxiliar para tratar dados salvos no banco ou retornar valor padrão (hoje)
def obter_data_salva(dados, index):
    if dados and dados[index]:
        try:
            return datetime.strptime(dados[index], "%Y-%m-%d").date()
        except ValueError:
            return datetime.today().date()
    return datetime.today().date()

# Preenche os campos se já houver registro no banco
orcamento_atual = float(dados_existentes[1]) if dados_existentes else 0.0

# ── FORMULÁRIO DE ENTRADA DE DADOS ───────────────────────────────────────────
with st.form("form_orcamento", clear_on_submit=False):
    
    st.subheader("💰 Aspectos Financeiros")
    v_orcamento = st.number_input(
        "Orçamento previsto (R$):", 
        min_value=0.0, 
        value=orcamento_atual, 
        format="%.2f"
    )
    
    st.divider()
    
    # Divisão visual em colunas para Datas Previstas vs Realizadas
    st.subheader("📅 Cronograma e Marcos do Projeto (Milestones)")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### 🗓️ Planejado & Abertura")
        d_inicio = st.date_input("Data de início do projeto (abertura CC):", obter_data_salva(dados_existentes, 2))
        p_viabilidade = st.date_input("Data PREVISTA de aprovação da Viabilidade:", obter_data_salva(dados_existentes, 3))
        p_qualidade = st.date_input("Data PREVISTA de aprovação nos Critérios de Qualidade:", obter_data_salva(dados_existentes, 4))
        p_aprov_lanc = st.date_input("Data PREVISTA de aprovação para Lançamento:", obter_data_salva(dados_existentes, 5))
        p_lancamento = st.date_input("Data PREVISTA de LANÇAMENTO:", obter_data_salva(dados_existentes, 6))

    with c2:
        st.markdown("### 🚀 Realizado")
        # Espaçador para alinhar com o campo de data de início da col1
        st.markdown("<div style='margin-top: 44px;'></div>", unsafe_allow_html=True) 
        
        r_viabilidade = st.date_input("Data REALIZADA de aprovação da Viabilidade:", obter_data_salva(dados_existentes, 7))
        r_qualidade = st.date_input("Data REALIZADA de aprovação nos Critérios de Qualidade:", obter_data_salva(dados_existentes, 8))
        r_aprov_lanc = st.date_input("Data REALIZADA de aprovação para Lançamento:", obter_data_salva(dados_existentes, 9))
        r_lancamento = st.date_input("Data REALIZADA de LANÇAMENTO:", obter_data_salva(dados_existentes, 10))

    st.markdown("<br>", unsafe_allow_html=True)
    botao_salvar = st.form_submit_button("💾 Salvar Dados do Projeto", type="primary")

# ── LÓGICA DE SALVAMENTO NO BANCO DE DADOS ───────────────────────────────────
if botao_salvar:
    try:
        conn = sqlite3.connect("dados_projetos.db")
        cursor = conn.cursor()
        
        # Insere ou Atualiza se o projeto já existir (UPSERT)
        cursor.execute("""
            INSERT INTO orcamentos_cronograma (
                projeto, orcamento_previsto, data_inicio, 
                prev_viabilidade, prev_qualidade, prev_aprov_lancamento, prev_lancamento,
                real_viabilidade, real_qualidade, real_aprov_lancamento, real_lancamento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(projeto) DO UPDATE SET
                orcamento_previsto=excluded.orcamento_previsto,
                data_inicio=excluded.data_inicio,
                prev_viabilidade=excluded.prev_viabilidade,
                prev_qualidade=excluded.prev_qualidade,
                prev_aprov_lancamento=excluded.prev_aprov_lancamento,
                prev_lancamento=excluded.prev_lancamento,
                real_viabilidade=excluded.real_viabilidade,
                real_qualidade=excluded.real_qualidade,
                real_aprov_lancamento=excluded.real_aprov_lancamento,
                real_lancamento=excluded.real_lancamento
        """, (
            cc_selecionado, v_orcamento, str(d_inicio),
            str(p_viabilidade), str(p_qualidade), str(p_aprov_lanc), str(p_lancamento),
            str(r_viabilidade), str(r_qualidade), str(r_aprov_lanc), str(r_lancamento)
        ))
        
        conn.commit()
        conn.close()
        
        # Limpa o cache para que as outras páginas vejam os novos dados imediatamente
        agregar_tudo.clear()
        
        st.success(f"✅ Dados do projeto **{cc_selecionado}** gravados e atualizados com sucesso!")
        st.toast("Banco de dados atualizado!", icon="💾")
        
    except Exception as e:
        st.error(f"❌ Erro ao salvar dados no banco: {e}")
