"""
auth.py — Camada de autenticação simples (hardcoded).
Gerencia sessão via st.session_state.

Perfis disponíveis:
  - "admin"      → acesso total
  - "visualizador" → somente leitura
"""
import streamlit as st
import hashlib

# ── Usuários hardcoded ────────────────────────────────────────────────────────
# Senhas armazenadas como SHA-256 para não ficarem em plaintext no código.
def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()

USUARIOS = {
    "admin": {
        "senha_hash": _hash("admin123!@#"),
        "perfil":     "admin",
        "nome":       "Administrador",
    },
    "mobilidadeeletrica": {
        "senha_hash": _hash("me123456"),
        "perfil":     "visualizador",
        "nome":       "Mobilidade Elétrica",
    },
}


# ── API pública ───────────────────────────────────────────────────────────────

def autenticado() -> bool:
    """Retorna True se há uma sessão válida."""
    return st.session_state.get("auth_ok", False)


def perfil_admin() -> bool:
    """Retorna True se o usuário logado é administrador."""
    return st.session_state.get("perfil") == "admin"


def validar_login(usuario: str, senha: str) -> bool:
    """Valida credenciais e, se corretas, grava a sessão."""
    user = USUARIOS.get(usuario.strip().lower())
    if user and user["senha_hash"] == _hash(senha):
        st.session_state["auth_ok"]  = True
        st.session_state["usuario"]  = usuario.strip().lower()
        st.session_state["perfil"]   = user["perfil"]
        st.session_state["nome"]     = user["nome"]
        return True
    return False


def logout() -> None:
    """Limpa completamente a sessão e força volta ao login."""
    for key in ["auth_ok", "usuario", "perfil", "nome"]:
        st.session_state.pop(key, None)
    st.rerun()


def exibir_login() -> None:
    """
    Renderiza a tela de login centralizada.
    Deve ser chamada em app.py antes de st.navigation() quando não autenticado.
    """
    # CSS da tela de login — compatível dark/light
    st.markdown("""
    <style>
    /* Oculta sidebar e toolbar na tela de login */
    section[data-testid="stSidebar"]       { display: none !important; }
    div[data-testid="stToolbar"]            { display: none !important; }
    header[data-testid="stHeader"]          { display: none !important; }

    /* Centraliza o card */
    .login-wrapper {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 80vh;
    }
    .login-card {
        width: 100%;
        max-width: 420px;
        padding: 40px 36px 32px;
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 16px;
        margin: 0 auto;
    }
    .login-logo {
        text-align: center;
        font-size: 48px;
        margin-bottom: 6px;
    }
    .login-title {
        text-align: center;
        font-size: 22px;
        font-weight: 700;
        margin-bottom: 4px;
        line-height: 1.35;
    }
    .login-sub {
        text-align: center;
        font-size: 13px;
        opacity: .55;
        margin-bottom: 28px;
    }
    </style>
    """, unsafe_allow_html=True)

    # Layout: coluna central estreita para simular card
    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown("<div class='login-logo'>📊</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='login-title'>Mobilidade Elétrica<br>"
            "<span style='font-size:16px;font-weight:500;opacity:.75'>Dashboard de Projetos</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='login-sub'>Faça login para continuar</div>", unsafe_allow_html=True)

        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input("Usuário", placeholder="Digite seu usuário")
            senha   = st.text_input("Senha",   placeholder="Digite sua senha", type="password")
            entrar  = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if entrar:
            if validar_login(usuario, senha):
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
