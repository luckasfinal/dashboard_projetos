import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in [str(ROOT), str(ROOT / "utils")]:
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ["PYTHONPATH"] = str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")

import streamlit as st
from utils.db import init_db, migrar_db

st.set_page_config(
    page_title="Dashboard de Projetos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inicializa e migra banco (cria colunas novas se o banco antigo existir)
init_db()
migrar_db()

pages = {
    "📤 Upload de Planilhas": [
        st.Page(str(ROOT / "pages" / "1_upload.py"), title="Upload de Planilhas", icon="📤"),
    ],
    "📊 Análises": [
        st.Page(str(ROOT / "pages" / "2_dashboard.py"), title="Dashboard Financeiro",   icon="📊"),
        st.Page(str(ROOT / "pages" / "3_projetos.py"),  title="Andamento dos Projetos", icon="📈"),
    ],
}

pg = st.navigation(pages)
pg.run()
