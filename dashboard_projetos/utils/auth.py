"""
auth.py — Autenticação obrigatória com credenciais fora do código.

Modelo de segurança (Streamlit Community Cloud):
  - NENHUM dado é renderizado antes do login (o app.py chama exigir_login()
    e dá st.stop() enquanto não há sessão autenticada).
  - As credenciais NÃO ficam no código. São lidas de:
      1. st.secrets  (produção — painel "Secrets" do Streamlit Cloud)
      2. variáveis de ambiente (alternativa local, ex: via .env exportado)
  - Senhas são comparadas por hash SHA-256 com comparação em tempo constante.

Formato esperado das credenciais (ver .env.example / secrets.toml):
  - AUTH_USERS: lista "usuario:perfil:hash_sha256_da_senha" separada por ';'
    Ex: "admin:admin:5e88...;consulta:visualizador:9f86..."
  Perfis válidos: "admin" (acesso total) e "visualizador" (somente leitura).

Gerar o hash de uma senha:
  python -c "import hashlib; print(hashlib.sha256('MINHA_SENHA'.encode()).hexdigest())"
"""
import os
import hmac
import hashlib
import streamlit as st


def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode("utf-8")).hexdigest()


# ── Carregamento de credenciais (secrets > env) ───────────────────────────────

def _ler_fonte_credenciais() -> str:
    """
    Retorna a string bruta de AUTH_USERS a partir de st.secrets (produção)
    ou variável de ambiente (local). String vazia se não configurado.
    """
    # 1) st.secrets — mecanismo nativo do Streamlit Cloud
    try:
        if "AUTH_USERS" in st.secrets:
            return str(st.secrets["AUTH_USERS"])
    except Exception:
        # st.secrets pode lançar se não houver secrets.toml; ignora e tenta env
        pass
    # 2) variável de ambiente (uso local)
    return os.environ.get("AUTH_USERS", "")


def _parse_usuarios(bruto: str) -> dict:
    """
    Converte "user:perfil:hash;user2:perfil2:hash2" em dict:
      { "user": {"perfil": ..., "senha_hash": ...}, ... }
    Entradas malformadas são ignoradas com segurança.
    """
    usuarios = {}
    for entrada in bruto.split(";"):
        entrada = entrada.strip()
        if not entrada:
            continue
        partes = entrada.split(":")
        if len(partes) != 3:
            continue
        nome, perfil, senha_hash = (p.strip() for p in partes)
        perfil = perfil.lower()
        if perfil not in ("admin", "visualizador"):
            continue
        if not nome or len(senha_hash) != 64:
            continue
        usuarios[nome.lower()] = {
            "perfil": perfil,
            "senha_hash": senha_hash.lower(),
            "nome": nome,
        }
    return usuarios


def carregar_usuarios() -> dict:
    """Carrega e faz cache leve dos usuários permitidos na sessão."""
    if "_auth_users_cache" not in st.session_state:
        st.session_state["_auth_users_cache"] = _parse_usuarios(_ler_fonte_credenciais())
    return st.session_state["_auth_users_cache"]


# ── Estado de sessão ──────────────────────────────────────────────────────────

def autenticado() -> bool:
    return st.session_state.get("auth_ok", False) is True


def perfil_admin() -> bool:
    return st.session_state.get("perfil") == "admin"


def validar_login(usuario: str, senha: str) -> bool:
    """Valida credenciais (comparação em tempo constante). Grava sessão se ok."""
    usuarios = carregar_usuarios()
    user = usuarios.get((usuario or "").strip().lower())
    if not user:
        return False
    informado = _hash(senha or "")
    # hmac.compare_digest evita timing attack na comparação do hash
    if hmac.compare_digest(informado, user["senha_hash"]):
        st.session_state["auth_ok"] = True
        st.session_state["perfil"]  = user["perfil"]
        st.session_state["nome"]    = user["nome"]
        st.session_state["usuario"] = user["nome"]
        return True
    return False


def logout() -> None:
    """Encerra a sessão e volta ao login."""
    for k in ("auth_ok", "perfil", "nome", "usuario"):
        st.session_state.pop(k, None)
    st.rerun()


# ── Gate de autenticação ──────────────────────────────────────────────────────

def exigir_login() -> None:
    """
    Porteiro do app. Se não autenticado, renderiza APENAS a tela de login e
    interrompe a execução com st.stop() — nenhum dado é lido ou exibido antes
    de um login bem-sucedido. Deve ser chamada no topo do app.py, logo após
    set_page_config e antes de qualquer init_db()/leitura de dados.
    """
    if autenticado():
        return

    usuarios = carregar_usuarios()

    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    div[data-testid="stToolbar"]     { display: none !important; }
    header[data-testid="stHeader"]   { display: none !important; }
    .login-logo  { text-align:center; font-size:48px; margin-bottom:6px; }
    .login-title { text-align:center; font-size:22px; font-weight:700; margin-bottom:4px; line-height:1.35; }
    .login-sub   { text-align:center; font-size:13px; opacity:.55; margin-bottom:28px; }
    </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown("<div class='login-logo'>🔒</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='login-title'>Mobilidade Elétrica<br>"
            "<span style='font-size:16px;font-weight:500;opacity:.75'>Dashboard de Projetos</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='login-sub'>Acesso restrito — informe suas credenciais</div>",
                    unsafe_allow_html=True)

        # Se não há credenciais configuradas, avisa o administrador e bloqueia.
        if not usuarios:
            st.error(
                "⚠️ Nenhuma credencial configurada. Defina **AUTH_USERS** nos "
                "*Secrets* do Streamlit Cloud (ou variável de ambiente local) "
                "antes de usar o app."
            )
            st.stop()

        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input("Usuário", placeholder="Digite seu usuário")
            senha   = st.text_input("Senha", placeholder="Digite sua senha", type="password")
            entrar  = st.form_submit_button("Entrar", type="primary", use_container_width=True)

        if entrar:
            if validar_login(usuario, senha):
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

    # Barra o resto do app: nada além do login é executado/renderizado.
    st.stop()
