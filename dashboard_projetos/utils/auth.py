"""
auth.py — Camada de autenticação simples (hardcoded).
Gerencia sessão via st.session_state.

Comportamento:
  - Por padrão, qualquer pessoa que abrir o link entra automaticamente
    como "visualizador" (somente leitura), sem tela de login.
  - Um botão "Alterar usuário" na sidebar leva à tela de login clássica,
    onde é possível entrar como administrador (ou visualizador novamente).

Perfis disponíveis:
  - "admin"        → acesso total
  - "visualizador" → somente leitura
"""
import streamlit as st
import hashlib

# ── Usuários hardcoded ────────────────────────────────────────────────────────
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

PERFIL_PADRAO = {
    "perfil":  "visualizador",
    "nome":    "Visitante",
    "usuario": None,
}


# ── API pública ───────────────────────────────────────────────────────────────

def garantir_sessao_padrao() -> None:
    """
    Garante que toda sessão tenha um perfil definido.
    Se a pessoa nunca fez login, entra automaticamente como visualizador.
    """
    if "perfil" not in st.session_state:
        st.session_state["perfil"]  = PERFIL_PADRAO["perfil"]
        st.session_state["nome"]    = PERFIL_PADRAO["nome"]
        st.session_state["usuario"] = PERFIL_PADRAO["usuario"]


def perfil_admin() -> bool:
    """Retorna True se o usuário logado é administrador."""
    return st.session_state.get("perfil") == "admin"


def mostrando_login() -> bool:
    return st.session_state.get("mostrar_login", False)


def solicitar_login() -> None:
    """Aciona a exibição da tela de login (botão 'Alterar usuário')."""
    st.session_state["mostrar_login"] = True


def cancelar_login() -> None:
    """Fecha a tela de login sem alterar o perfil atual."""
    st.session_state.pop("mostrar_login", None)


def validar_login(usuario: str, senha: str) -> bool:
    """Valida credenciais e, se corretas, grava a sessão e fecha o login."""
    user = USUARIOS.get(usuario.strip().lower())
    if user and user["senha_hash"] == _hash(senha):
        st.session_state["perfil"]   = user["perfil"]
        st.session_state["nome"]     = user["nome"]
        st.session_state["usuario"]  = usuario.strip().lower()
        st.session_state.pop("mostrar_login", None)
        return True
    return False


def voltar_para_visualizador() -> None:
    """Sai do modo administrador e retorna ao perfil padrão (visualizador)."""
    st.session_state["perfil"]  = PERFIL_PADRAO["perfil"]
    st.session_state["nome"]    = PERFIL_PADRAO["nome"]
    st.session_state["usuario"] = PERFIL_PADRAO["usuario"]
    st.session_state.pop("mostrar_login", None)


def exibir_login() -> None:
    """
    Renderiza a tela de login clássica, centralizada.
    Inclui botão "Voltar" para fechar sem autenticar.
    """
    st.markdown("""
    <style>
    section[data-testid="stSidebar"]       { display: none !important; }
    div[data-testid="stToolbar"]            { display: none !important; }
    header[data-testid="stHeader"]          { display: none !important; }

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

    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown("<div class='login-logo'>📊</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='login-title'>Mobilidade Elétrica<br>"
            "<span style='font-size:16px;font-weight:500;opacity:.75'>Dashboard de Projetos</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='login-sub'>Entre com suas credenciais de administrador</div>", unsafe_allow_html=True)

        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input("Usuário", placeholder="Digite seu usuário")
            senha   = st.text_input("Senha",   placeholder="Digite sua senha", type="password")
            c1, c2  = st.columns(2)
            entrar    = c1.form_submit_button("Entrar", type="primary", use_container_width=True)
            cancelar  = c2.form_submit_button("Voltar", use_container_width=True)

        if cancelar:
            cancelar_login()
            st.rerun()

        if entrar:
            if validar_login(usuario, senha):
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
