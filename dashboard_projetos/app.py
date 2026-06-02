import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in [str(ROOT), str(ROOT / "utils")]:
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")

import streamlit as st
from utils.db   import init_db, migrar_db
from utils.auth import autenticado, exibir_login, logout, perfil_admin

st.set_page_config(
    page_title="Dashboard de Projetos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)

# Inicializa e migra banco (cria colunas novas se o banco antigo existir)
init_db()
migrar_db()

# ── Guard de autenticação ─────────────────────────────────────────────────────
# Se não autenticado: mostra login e para aqui. Nenhuma página é montada.
if not autenticado():
    exibir_login()
    st.stop()

# ── Usuário autenticado — monta sidebar com info + logout ────────────────────
with st.sidebar:
    nome   = st.session_state.get("nome", "")
    perfil = st.session_state.get("perfil", "")
    icone  = "🔑" if perfil == "admin" else "👁️"
    badge  = "Administrador" if perfil == "admin" else "Visualizador"

    st.markdown(f"""
    <div style="padding:10px 4px 14px;border-bottom:1px solid rgba(128,128,128,.2);margin-bottom:8px">
        <div style="font-size:13px;font-weight:700">{icone} {nome}</div>
        <div style="font-size:11px;opacity:.55;margin-top:2px">{badge}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Sair", use_container_width=True):
        logout()

# ── Páginas — visíveis para ambos os perfis ───────────────────────────────────
# O controle de ações (salvar/upload/deletar) é feito dentro de cada página
# lendo st.session_state["perfil"].
pages = {
    "📤 Dados": [
        st.Page(str(ROOT / "pages" / "0_orcamento.py"), title="Orçamentos",          icon="📋"),
        st.Page(str(ROOT / "pages" / "1_upload.py"),    title="Upload de Arquivos",   icon="📤"),
    ],
    "📊 Análises": [
        st.Page(str(ROOT / "pages" / "2_dashboard.py"), title="Dashboard Financeiro", icon="📊"),
        st.Page(str(ROOT / "pages" / "3_projetos.py"),  title="Andamento dos Projetos", icon="📈"),
    ],
}

pg = st.navigation(pages)
pg.run()
