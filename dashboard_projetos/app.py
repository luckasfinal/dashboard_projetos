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
from utils.auth import exigir_login, perfil_admin, logout

st.set_page_config(
    page_title="Dashboard de Projetos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 5.4 — Ajustes responsivos globais (mobile) ────────────────────────────────
# Reduz paddings, fontes de KPI e força colunas a empilhar em telas estreitas.
st.markdown("""
<style>
/* Em telas estreitas, colunas do Streamlit empilham em vez de espremer */
@media (max-width: 640px) {
    div[data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
        gap: 6px !important;
    }
    div[data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
    }
    /* KPI um pouco menor no mobile para não cortar */
    div[data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 18px !important;
    }
    /* Reduz padding lateral do conteúdo principal */
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    /* Títulos um pouco menores */
    h1 { font-size: 1.5rem !important; }
    h2 { font-size: 1.2rem !important; }
}
/* Tabelas roláveis horizontalmente em qualquer tela estreita */
div[data-testid="stDataFrame"] { overflow-x: auto; }
</style>
""", unsafe_allow_html=True)

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

# ── GATE DE AUTENTICAÇÃO ──────────────────────────────────────────────────────
# Barreira obrigatória: se não autenticado, exigir_login() renderiza só a tela
# de login e chama st.stop(). Como init_db/migrar_db apenas garantem o schema
# (não expõem dados), e nenhuma PÁGINA roda antes de pg.run() lá embaixo,
# nenhum dado de projeto é lido ou renderizado sem login bem-sucedido.
exigir_login()

# Daqui em diante, o usuário está autenticado.
admin = perfil_admin()

# ── Sidebar: perfil atual + logout ────────────────────────────────────────────
with st.sidebar:
    nome  = st.session_state.get("nome", "Usuário")
    icone = "🔑" if admin else "👁️"
    badge = "Administrador" if admin else "Visualizador"

    st.markdown(f"""
    <div style="padding:10px 4px 14px;border-bottom:1px solid rgba(128,128,128,.2);margin-bottom:8px">
        <div style="font-size:13px;font-weight:700">{icone} {nome}</div>
        <div style="font-size:11px;opacity:.55;margin-top:2px">{badge}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 Sair", use_container_width=True):
        logout()

    # ── Onboarding mínimo: fluxo de uso ───────────────────────────────────────
    with st.expander("❓ Como usar este painel"):
        st.markdown(
            "**Fluxo recomendado:**\n\n"
            "1. **📤 Upload de Arquivos** — importe as planilhas de custos e horas.\n"
            "2. **📋 Orçamentos** — cadastre orçamento, status e datas de cada projeto.\n"
            "3. **📊 Dashboard Financeiro** — acompanhe custos e orçamento.\n"
            "4. **📈 Andamento dos Projetos** — acompanhe prazos, status e alertas.\n\n"
            "Use os **filtros** na barra lateral para focar em projetos, anos ou status. "
            "Passe o mouse sobre os indicadores para ver o **valor exato**."
        )

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
