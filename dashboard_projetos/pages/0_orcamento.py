import sys
from pathlib import Path
from datetime import datetime, date

_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from utils.db import init_db, migrar_db, salvar_orcamento, carregar_orcamento_projeto
from utils.data_processor import agregar_tudo, formata_brl

init_db()
migrar_db()

st.title("📋 Planejamento de Orçamentos e Prazos")
st.markdown("Insira ou atualize o orçamento e o cronograma de marcos dos projetos.")

# ── 1. Projetos disponíveis ───────────────────────────────────────────────────
df_dashboard, _, _ = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum projeto encontrado. Importe as planilhas na página de Upload.")
    st.stop()

lista_cc = sorted(df_dashboard["projeto"].unique().tolist())
mapeamento_nomes = dict(zip(df_dashboard["projeto"], df_dashboard["nome_projeto"]))

cc_selecionado = st.selectbox(
    "Selecione o Centro de Custo (CC) do Projeto:",
    options=lista_cc,
    format_func=lambda x: f"{x} — {mapeamento_nomes.get(x, 'Sem Nome')}"
)

# ── 2. Dados já salvos ────────────────────────────────────────────────────────
dados = carregar_orcamento_projeto(cc_selecionado)

def _parse_date_or_none(valor) -> date | None:
    """Retorna date se válido, None para campo vazio."""
    if valor and str(valor) not in ("0", "None", "nan", ""):
        try:
            return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return None

def _str_or_none(d) -> str | None:
    return str(d) if d is not None else None

def _tem(chave: str) -> bool:
    """True se já existe data salva no banco para esta chave."""
    return bool(dados and _parse_date_or_none(dados.get(chave)))

def _ind(chave: str) -> str:
    """Retorna '🔵 ' se o campo já tem dado salvo (sinaliza que será atualizado)."""
    return "🔵 " if _tem(chave) else ""

orcamento_atual = float(dados["orcamento_previsto"]) if dados and dados.get("orcamento_previsto") else 0.0
orc_tem_dado    = dados and dados.get("orcamento_previsto") and float(dados["orcamento_previsto"]) > 0

realizado_proj = 0.0
linha = df_dashboard[df_dashboard["projeto"] == cc_selecionado]
if not linha.empty:
    realizado_proj = float(linha.iloc[0].get("valor_total", 0))

# ── 3. Formulário ─────────────────────────────────────────────────────────────
with st.form("form_orcamento", clear_on_submit=False):

    # — Financeiro ————————————————————————————————————————————————————————————
    st.subheader("💰 Orçamento")
    col_fin1, col_fin2 = st.columns(2)
    with col_fin1:
        label_orc = f"{'🔵 ' if orc_tem_dado else ''}Orçamento previsto (R$):"
        v_orcamento = st.number_input(
            label_orc,
            min_value=0.0, value=orcamento_atual, format="%.2f"
        )
    with col_fin2:
        st.text_input(
            "Orçamento realizado (R$) — somente leitura:",
            value=formata_brl(realizado_proj),
            disabled=True,
            help="Calculado automaticamente a partir dos lançamentos importados."
        )

    st.divider()

    # — Cronograma ─────────────────────────────────────────────────────────────
    st.subheader("📅 Cronograma de Marcos")
    st.caption("🔵 indica campo com dado já salvo — Marcar 'Limpar' removerá a data ao salvar.")

    # Cabeçalho
    h1, h2, h3 = st.columns([2, 2, 2])
    h1.markdown("**Marco**")
    h2.markdown("**🗓️ Data Prevista**")
    h3.markdown("**✅ Data Realizada**")
    st.markdown("<hr style='margin:4px 0 12px 0'>", unsafe_allow_html=True)

    # Valores iniciais do banco
    v = {k: _parse_date_or_none(dados.get(k)) if dados else None for k in [
        "data_inicio",
        "prev_viabilidade",      "real_viabilidade",
        "prev_qualidade",        "real_qualidade",
        "prev_aprov_lancamento", "real_aprov_lancamento",
        "prev_lancamento",       "real_lancamento",
    ]}

    # Linha 1 — Início
    r1c1, r1c2, r1c3 = st.columns([2, 2, 2])
    r1c1.markdown(f"**{_ind('data_inicio')}Início do Projeto**<br><small>(abertura CC)</small>", unsafe_allow_html=True)
    with r1c2:
        d_inicio = st.date_input("##inicio_prev", value=v["data_inicio"], format="DD/MM/YYYY", label_visibility="collapsed")
        if v["data_inicio"]:
            if st.checkbox("Limpar", key="clear_data_inicio", help="Marque para remover esta data"):
                d_inicio = None
    r1c3.markdown("<div style='padding-top:8px;color:#666;font-size:13px'><i>Mesma da previsão</i></div>", unsafe_allow_html=True)

    # Linha 2 — Viabilidade
    r2c1, r2c2, r2c3 = st.columns([2, 2, 2])
    r2c1.markdown(f"**{_ind('prev_viabilidade')}Aprovação da Viabilidade**")
    with r2c2:
        p_viabilidade = st.date_input("##viab_prev", value=v["prev_viabilidade"], format="DD/MM/YYYY", label_visibility="collapsed")
        if v["prev_viabilidade"]:
            if st.checkbox("Limpar", key="clear_prev_viab", help="Marque para remover esta data"):
                p_viabilidade = None
    with r2c3:
        r_viabilidade = st.date_input(
            f"##viab_real{'🔵' if _tem('real_viabilidade') else ''}",
            value=v["real_viabilidade"], format="DD/MM/YYYY", label_visibility="collapsed"
        )
        if v["real_viabilidade"]:
            if st.checkbox("Limpar", key="clear_real_viab", help="Marque para remover esta data"):
                r_viabilidade = None

    # Linha 3 — Qualidade
    r3c1, r3c2, r3c3 = st.columns([2, 2, 2])
    r3c1.markdown(f"**{_ind('prev_qualidade')}Critérios de Qualidade**")
    with r3c2:
        p_qualidade = st.date_input("##qual_prev", value=v["prev_qualidade"], format="DD/MM/YYYY", label_visibility="collapsed")
        if v["prev_qualidade"]:
            if st.checkbox("Limpar", key="clear_prev_qual", help="Marque para remover esta data"):
                p_qualidade = None
    with r3c3:
        r_qualidade = st.date_input(
            f"##qual_real{'🔵' if _tem('real_qualidade') else ''}",
            value=v["real_qualidade"], format="DD/MM/YYYY", label_visibility="collapsed"
        )
        if v["real_qualidade"]:
            if st.checkbox("Limpar", key="clear_real_qual", help="Marque para remover esta data"):
                r_qualidade = None

    # Linha 4 — Aprovação para Lançamento
    r4c1, r4c2, r4c3 = st.columns([2, 2, 2])
    r4c1.markdown(f"**{_ind('prev_aprov_lancamento')}Aprovação para Lançamento**")
    with r4c2:
        p_aprov_lanc = st.date_input("##aprov_prev", value=v["prev_aprov_lancamento"], format="DD/MM/YYYY", label_visibility="collapsed")
        if v["prev_aprov_lancamento"]:
            if st.checkbox("Limpar", key="clear_prev_aprov", help="Marque para remover esta data"):
                p_aprov_lanc = None
    with r4c3:
        r_aprov_lanc = st.date_input(
            f"##aprov_real{'🔵' if _tem('real_aprov_lancamento') else ''}",
            value=v["real_aprov_lancamento"], format="DD/MM/YYYY", label_visibility="collapsed"
        )
        if v["real_aprov_lancamento"]:
            if st.checkbox("Limpar", key="clear_real_aprov", help="Marque para remover esta data"):
                r_aprov_lanc = None

    # Linha 5 — Lançamento
    r5c1, r5c2, r5c3 = st.columns([2, 2, 2])
    r5c1.markdown(f"**{_ind('prev_lancamento')}🚀 LANÇAMENTO**")
    with r5c2:
        p_lancamento = st.date_input("##lanc_prev", value=v["prev_lancamento"], format="DD/MM/YYYY", label_visibility="collapsed")
        if v["prev_lancamento"]:
            if st.checkbox("Limpar", key="clear_prev_lanc", help="Marque para remover esta data"):
                p_lancamento = None
    with r5c3:
        r_lancamento = st.date_input(
            f"##lanc_real{'🔵' if _tem('real_lancamento') else ''}",
            value=v["real_lancamento"], format="DD/MM/YYYY", label_visibility="collapsed"
        )
        if v["real_lancamento"]:
            if st.checkbox("Limpar", key="clear_real_lanc", help="Marque para remover esta data"):
                r_lancamento = None

    st.markdown("<br>", unsafe_allow_html=True)
    botao_salvar = st.form_submit_button("💾 Salvar Dados do Projeto", type="primary")

# ── 4. Salvamento ─────────────────────────────────────────────────────────────
if botao_salvar:
    try:
        salvar_orcamento(
            projeto               = cc_selecionado,
            orcamento_previsto    = v_orcamento,
            data_inicio           = _str_or_none(d_inicio),
            prev_viabilidade      = _str_or_none(p_viabilidade),
            prev_qualidade        = _str_or_none(p_qualidade),
            prev_aprov_lancamento = _str_or_none(p_aprov_lanc),
            prev_lancamento       = _str_or_none(p_lancamento),
            real_viabilidade      = _str_or_none(r_viabilidade),
            real_qualidade        = _str_or_none(r_qualidade),
            real_aprov_lancamento = _str_or_none(r_aprov_lanc),
            real_lancamento       = _str_or_none(r_lancamento),
        )
        agregar_tudo.clear()
        st.success(f"✅ Dados do projeto **{cc_selecionado}** gravados com sucesso!")
        st.toast("Banco de dados updated!", icon="💾")
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")

# ── 5. Resumo pós-salvo ───────────────────────────────────────────────────────
st.divider()
st.subheader(f"📊 Resumo — {cc_selecionado} / {mapeamento_nomes.get(cc_selecionado, '')}")

dados_atuais = carregar_orcamento_projeto(cc_selecionado)
if dados_atuais:
    orc_prev = float(dados_atuais.get("orcamento_previsto") or 0)
    saldo    = orc_prev - realizado_proj
    pct      = (realizado_proj / orc_prev * 100) if orc_prev > 0 else 0

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Orçamento Previsto", formata_brl(orc_prev))
    col_b.metric("Realizado (custos)", formata_brl(realizado_proj))
    col_c.metric("Saldo", formata_brl(saldo), delta=f"{pct:.1f}% consumido", delta_color="inverse")

    def _fmt(val) -> str:
        if not val or str(val) in ("0", "None", "nan", ""):
            return "—"
        try:
            return datetime.strptime(str(val)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return str(val)

    def _delta(prev, real) -> str:
        if not prev or not real or str(prev) in ("0","None","") or str(real) in ("0","None",""):
            return "—"
        try:
            dp = datetime.strptime(str(prev)[:10], "%Y-%m-%d")
            dr = datetime.strptime(str(real)[:10], "%Y-%m-%d")
            diff = (dr - dp).days
            if diff > 0:  return f"🔴 +{diff} dias"
            if diff < 0:  return f"🟢 {abs(diff)} dias adiantado"
            return "✅ No prazo"
        except Exception:
            return "—"

    marcos = [
        ("Início do Projeto (abertura CC)", dados_atuais.get("data_inicio"),           dados_atuais.get("data_inicio")),
        ("Aprovação da Viabilidade",         dados_atuais.get("prev_viabilidade"),      dados_atuais.get("real_viabilidade")),
        ("Critérios de Qualidade",           dados_atuais.get("prev_qualidade"),        dados_atuais.get("real_qualidade")),
        ("Aprovação para Lançamento",        dados_atuais.get("prev_aprov_lancamento"), dados_atuais.get("real_aprov_lancamento")),
        ("🚀 LANÇAMENTO",                   dados_atuais.get("prev_lancamento"),        dados_atuais.get("real_lancamento")),
    ]

    df_marcos = pd.DataFrame([
        {
            "Marco":     nome,
            "Previsto":  _fmt(prev),
            "Realizado": _fmt(real) if real is not None else "—",
            "Situação":  _delta(prev, real) if real is not None else "—",
        }
        for nome, prev, real in marcos
    ])

    def _highlight(row):
        sit = row["Situação"]
        if "🔴" in str(sit):
            return ["", "", "background-color:#fde8e8", "background-color:#fde8e8; color:#900"]
        if "🟢" in str(sit):
            return ["", "", "background-color:#e8fde8", "background-color:#e8fde8; color:#060"]
        if "✅" in str(sit):
            return ["", "", "background-color:#eaf4fb", "background-color:#eaf4fb; color:#1a5276"]
        return ["", "", "", ""]

    st.dataframe(
        df_marcos.style.apply(_highlight, axis=1),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Preencha o formulário acima e salve para ver o resumo.")
