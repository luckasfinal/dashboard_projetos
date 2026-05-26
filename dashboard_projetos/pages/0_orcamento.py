import sys
from pathlib import Path
from datetime import datetime, date

_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from utils.db import init_db, migrar_db, salvar_orcamento, carregar_orcamento_projeto
from utils.data_processor import agregar_tudo, formata_brl

init_db()
migrar_db()

st.title("📋 Planejamento de Orçamentos e Prazos")
st.markdown("Insira ou atualize o orçamento e o cronograma de marcos (Milestones) dos projetos.")

# ── 1. Carrega projetos disponíveis ──────────────────────────────────────────
df_dashboard, df_custos_raw, _ = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum projeto encontrado no banco de dados. Importe as planilhas primeiro na página de Upload.")
    st.stop()

lista_cc = sorted(df_dashboard["projeto"].unique().tolist())
mapeamento_nomes = dict(zip(df_dashboard["projeto"], df_dashboard["nome_projeto"]))

cc_selecionado = st.selectbox(
    "Selecione o Centro de Custo (CC) do Projeto:",
    options=lista_cc,
    format_func=lambda x: f"{x} — {mapeamento_nomes.get(x, 'Sem Nome')}"
)

# ── 2. Busca dados já salvos para o projeto selecionado ──────────────────────
dados = carregar_orcamento_projeto(cc_selecionado)

def _parse_date(valor) -> date:
    """Converte string 'YYYY-MM-DD' para date, ou retorna hoje."""
    if valor:
        try:
            return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return datetime.today().date()

def _str_or_none(d: date) -> str | None:
    return str(d) if d else None

# Valores pré-preenchidos
orcamento_atual       = float(dados["orcamento_previsto"]) if dados and dados.get("orcamento_previsto") else 0.0
d_inicio_val          = _parse_date(dados.get("data_inicio"))           if dados else datetime.today().date()
p_viabilidade_val     = _parse_date(dados.get("prev_viabilidade"))      if dados else datetime.today().date()
p_qualidade_val       = _parse_date(dados.get("prev_qualidade"))        if dados else datetime.today().date()
p_aprov_lanc_val      = _parse_date(dados.get("prev_aprov_lancamento")) if dados else datetime.today().date()
p_lancamento_val      = _parse_date(dados.get("prev_lancamento"))       if dados else datetime.today().date()
r_viabilidade_val     = _parse_date(dados.get("real_viabilidade"))      if dados else datetime.today().date()
r_qualidade_val       = _parse_date(dados.get("real_qualidade"))        if dados else datetime.today().date()
r_aprov_lanc_val      = _parse_date(dados.get("real_aprov_lancamento")) if dados else datetime.today().date()
r_lancamento_val      = _parse_date(dados.get("real_lancamento"))       if dados else datetime.today().date()

# Orçamento realizado (somente leitura — vem da planilha de custos)
realizado_projeto = 0.0
if not df_dashboard.empty:
    linha = df_dashboard[df_dashboard["projeto"] == cc_selecionado]
    if not linha.empty:
        realizado_projeto = float(linha.iloc[0].get("valor_total", 0))

# ── 3. Formulário ─────────────────────────────────────────────────────────────
with st.form("form_orcamento", clear_on_submit=False):

    st.subheader("💰 Aspectos Financeiros")

    col_fin1, col_fin2 = st.columns(2)
    with col_fin1:
        v_orcamento = st.number_input(
            "Orçamento previsto (R$):",
            min_value=0.0,
            value=orcamento_atual,
            format="%.2f",
            help="Valor total aprovado para o projeto."
        )
    with col_fin2:
        st.text_input(
            "Orçamento realizado (R$) — planilha de custos:",
            value=formata_brl(realizado_projeto),
            disabled=True,
            help="Valor calculado automaticamente a partir dos lançamentos importados. Não é editável aqui."
        )

    st.divider()
    st.subheader("📅 Cronograma e Marcos do Projeto (Milestones)")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### 🗓️ Planejado & Abertura")
        d_inicio      = st.date_input("Data de início do projeto (abertura CC):", value=d_inicio_val)
        p_viabilidade = st.date_input("Data PREVISTA — Aprovação da Viabilidade:", value=p_viabilidade_val)
        p_qualidade   = st.date_input("Data PREVISTA — Aprovação nos Critérios de Qualidade:", value=p_qualidade_val)
        p_aprov_lanc  = st.date_input("Data PREVISTA — Aprovação para Lançamento:", value=p_aprov_lanc_val)
        p_lancamento  = st.date_input("Data PREVISTA — LANÇAMENTO:", value=p_lancamento_val)

    with c2:
        st.markdown("### 🚀 Realizado")
        st.markdown("<div style='margin-top: 44px;'></div>", unsafe_allow_html=True)
        r_viabilidade = st.date_input("Data REALIZADA — Aprovação da Viabilidade:", value=r_viabilidade_val)
        r_qualidade   = st.date_input("Data REALIZADA — Aprovação nos Critérios de Qualidade:", value=r_qualidade_val)
        r_aprov_lanc  = st.date_input("Data REALIZADA — Aprovação para Lançamento:", value=r_aprov_lanc_val)
        r_lancamento  = st.date_input("Data REALIZADA — LANÇAMENTO:", value=r_lancamento_val)

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
        st.error(f"❌ Erro ao salvar dados no banco: {e}")

# ── 5. Resumo do projeto selecionado (pós-salvo) ──────────────────────────────
st.divider()
st.subheader(f"📊 Resumo — {cc_selecionado} / {mapeamento_nomes.get(cc_selecionado, '')}")

dados_atuais = carregar_orcamento_projeto(cc_selecionado)
if dados_atuais:
    col_a, col_b, col_c = st.columns(3)
    orc_prev = float(dados_atuais.get("orcamento_previsto") or 0)
    saldo    = orc_prev - realizado_projeto
    pct      = (realizado_projeto / orc_prev * 100) if orc_prev > 0 else 0

    col_a.metric("Orçamento Previsto", formata_brl(orc_prev))
    col_b.metric("Realizado (custos)", formata_brl(realizado_projeto))
    col_c.metric(
        "Saldo",
        formata_brl(saldo),
        delta=f"{pct:.1f}% consumido",
        delta_color="inverse"
    )

    # Tabela de marcos
    marcos = {
        "Marco": [
            "Início do Projeto (abertura CC)",
            "Aprovação da Viabilidade",
            "Aprovação — Critérios de Qualidade",
            "Aprovação para Lançamento",
            "LANÇAMENTO",
        ],
        "Previsto": [
            dados_atuais.get("data_inicio") or "—",
            dados_atuais.get("prev_viabilidade") or "—",
            dados_atuais.get("prev_qualidade") or "—",
            dados_atuais.get("prev_aprov_lancamento") or "—",
            dados_atuais.get("prev_lancamento") or "—",
        ],
        "Realizado": [
            "—",  # data de início não tem "realizado" separado
            dados_atuais.get("real_viabilidade") or "—",
            dados_atuais.get("real_qualidade") or "—",
            dados_atuais.get("real_aprov_lancamento") or "—",
            dados_atuais.get("real_lancamento") or "—",
        ],
    }

    import pandas as pd
    df_marcos = pd.DataFrame(marcos)

    # Destaca atrasos (realizado > previsto) em vermelho
    def _highlight_atraso(row):
        styles = ["", "", ""]
        prev = row["Previsto"]
        real = row["Realizado"]
        if prev != "—" and real != "—":
            try:
                dp = datetime.strptime(prev[:10], "%Y-%m-%d")
                dr = datetime.strptime(real[:10], "%Y-%m-%d")
                if dr > dp:
                    styles[2] = "background-color: #fde8e8; color: #900"
                else:
                    styles[2] = "background-color: #e8fde8; color: #060"
            except Exception:
                pass
        return styles

    st.dataframe(
        df_marcos.style.apply(_highlight_atraso, axis=1),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Nenhum dado salvo ainda para este projeto. Preencha o formulário acima e salve.")
