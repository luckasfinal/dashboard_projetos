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

def _parse_date(valor) -> date:
    if valor and str(valor) not in ("0", "None", "nan"):
        try:
            return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return datetime.today().date()

def _str_or_none(d) -> str | None:
    return str(d) if d else None

orcamento_atual  = float(dados["orcamento_previsto"]) if dados and dados.get("orcamento_previsto") else 0.0
realizado_proj   = 0.0
linha = df_dashboard[df_dashboard["projeto"] == cc_selecionado]
if not linha.empty:
    realizado_proj = float(linha.iloc[0].get("valor_total", 0))

# ── 3. Formulário ─────────────────────────────────────────────────────────────
with st.form("form_orcamento", clear_on_submit=False):

    # — Financeiro ————————————————————————————————————————————————————————————
    st.subheader("💰 Orçamento")
    col_fin1, col_fin2 = st.columns(2)
    with col_fin1:
        v_orcamento = st.number_input(
            "Orçamento previsto (R$):",
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

    # — Marcos: cabeçalho fixo + uma linha por marco ───────────────────────────
    st.subheader("📅 Cronograma de Marcos")

    # Cabeçalho das 3 colunas
    h1, h2, h3 = st.columns([2, 2, 2])
    h1.markdown("**Marco**")
    h2.markdown("**🗓️ Data Prevista**")
    h3.markdown("**✅ Data Realizada**")

    st.markdown("<hr style='margin:4px 0 12px 0'>", unsafe_allow_html=True)

    # Linha 1 — Início (só tem previsto)
    r1c1, r1c2, r1c3 = st.columns([2, 2, 2])
    r1c1.markdown("**Início do Projeto**<br><small>(abertura CC)</small>", unsafe_allow_html=True)
    d_inicio = r1c2.date_input("##inicio_prev", value=_parse_date(dados.get("data_inicio") if dados else None), label_visibility="collapsed")
    r1c3.markdown("<div style='padding-top:8px;color:#888;font-size:13px'>—</div>", unsafe_allow_html=True)

    # Linha 2 — Viabilidade
    r2c1, r2c2, r2c3 = st.columns([2, 2, 2])
    r2c1.markdown("**Aprovação da Viabilidade**", unsafe_allow_html=True)
    p_viabilidade = r2c2.date_input("##viab_prev", value=_parse_date(dados.get("prev_viabilidade") if dados else None), label_visibility="collapsed")
    r_viabilidade = r2c3.date_input("##viab_real", value=_parse_date(dados.get("real_viabilidade") if dados else None), label_visibility="collapsed")

    # Linha 3 — Qualidade
    r3c1, r3c2, r3c3 = st.columns([2, 2, 2])
    r3c1.markdown("**Critérios de Qualidade**", unsafe_allow_html=True)
    p_qualidade = r3c2.date_input("##qual_prev", value=_parse_date(dados.get("prev_qualidade") if dados else None), label_visibility="collapsed")
    r_qualidade = r3c3.date_input("##qual_real", value=_parse_date(dados.get("real_qualidade") if dados else None), label_visibility="collapsed")

    # Linha 4 — Aprovação para Lançamento
    r4c1, r4c2, r4c3 = st.columns([2, 2, 2])
    r4c1.markdown("**Aprovação para Lançamento**", unsafe_allow_html=True)
    p_aprov_lanc = r4c2.date_input("##aprov_prev", value=_parse_date(dados.get("prev_aprov_lancamento") if dados else None), label_visibility="collapsed")
    r_aprov_lanc = r4c3.date_input("##aprov_real", value=_parse_date(dados.get("real_aprov_lancamento") if dados else None), label_visibility="collapsed")

    # Linha 5 — Lançamento
    r5c1, r5c2, r5c3 = st.columns([2, 2, 2])
    r5c1.markdown("**🚀 LANÇAMENTO**", unsafe_allow_html=True)
    p_lancamento = r5c2.date_input("##lanc_prev", value=_parse_date(dados.get("prev_lancamento") if dados else None), label_visibility="collapsed")
    r_lancamento = r5c3.date_input("##lanc_real", value=_parse_date(dados.get("real_lancamento") if dados else None), label_visibility="collapsed")

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
        st.toast("Banco de dados atualizado!", icon="💾")
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
    col_a.metric("Orçamento Previsto",  formata_brl(orc_prev))
    col_b.metric("Realizado (custos)",  formata_brl(realizado_proj))
    col_c.metric("Saldo", formata_brl(saldo), delta=f"{pct:.1f}% consumido", delta_color="inverse")

    # Tabela de marcos com comparativo previsto x realizado e indicador de atraso
    def _fmt(val) -> str:
        if not val or str(val) in ("0", "None", "nan"):
            return "—"
        try:
            return datetime.strptime(str(val)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return str(val)

    def _delta(prev, real) -> str:
        if not prev or not real or str(prev) in ("0","None") or str(real) in ("0","None"):
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
        ("Início do Projeto (abertura CC)", dados_atuais.get("data_inicio"),           None),
        ("Aprovação da Viabilidade",         dados_atuais.get("prev_viabilidade"),      dados_atuais.get("real_viabilidade")),
        ("Critérios de Qualidade",           dados_atuais.get("prev_qualidade"),        dados_atuais.get("real_qualidade")),
        ("Aprovação para Lançamento",        dados_atuais.get("prev_aprov_lancamento"), dados_atuais.get("real_aprov_lancamento")),
        ("🚀 LANÇAMENTO",                   dados_atuais.get("prev_lancamento"),        dados_atuais.get("real_lancamento")),
    ]

    df_marcos = pd.DataFrame([
        {
            "Marco":    nome,
            "Previsto": _fmt(prev),
            "Realizado": _fmt(real) if real is not None else "—",
            "Situação": _delta(prev, real) if real is not None else "—",
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
