import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in [str(ROOT), str(ROOT / "utils")]:
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")

import streamlit as st
import streamlit.components.v1 as components
from utils.db   import init_db, migrar_db
from utils.auth import (
    garantir_sessao_padrao, perfil_admin, mostrando_login,
    exibir_login, solicitar_login, voltar_para_visualizador,
)

st.set_page_config(
    page_title="Dashboard de Projetos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── SEO / privacidade: solicita não-indexação a crawlers e IAs ────────────────
# Best-effort: injeta <meta name="robots"> no <head> do documento pai.
# Streamlit não expõe o <head> diretamente, então usamos um componente HTML
# que manipula window.parent.document (mesmo domínio em produção).
components.html("""
<script>
try {
  var head = window.parent.document.head;
  if (!head.querySelector('meta[name="robots"]')) {
    var meta = window.parent.document.createElement('meta');
    meta.name = 'robots';
    meta.content = 'noindex, nofollow, noarchive, nosnippet';
    head.appendChild(meta);
  }
} catch (e) {}
</script>
""", height=0, width=0)

init_db()
migrar_db()

garantir_sessao_padrao()

# ── Tela de login clássica (acionada via botão "Alterar usuário") ────────────
if mostrando_login():
    exibir_login()
    st.stop()

# ── Sidebar: perfil atual + ação de troca de usuário ─────────────────────────
with st.sidebar:
    nome   = st.session_state.get("nome", "Visitante")
    admin  = perfil_admin()
    icone  = "🔑" if admin else "👁️"
    badge  = "Administrador" if admin else "Visualizador"

    st.markdown(f"""
    <div style="padding:10px 4px 14px;border-bottom:1px solid rgba(128,128,128,.2);margin-bottom:8px">
        <div style="font-size:13px;font-weight:700">{icone} {nome}</div>
        <div style="font-size:11px;opacity:.55;margin-top:2px">{badge}</div>
    </div>
    """, unsafe_allow_html=True)

    if admin:
        if st.button("🔓 Sair do modo Admin", use_container_width=True):
            voltar_para_visualizador()
            st.rerun()
    else:
        if st.button("🔑 Alterar usuário", use_container_width=True):
            solicitar_login()
            st.rerun()

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
