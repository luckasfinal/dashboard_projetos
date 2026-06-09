import sys, io
from pathlib import Path
from datetime import datetime, date

_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from utils.db import (
    init_db, migrar_db,
    salvar_orcamento, carregar_orcamento_projeto,
    salvar_previsao_periodo, carregar_previsoes_projeto,
    deletar_previsao_periodo, deletar_projeto_completo,
    carregar_orcamentos,
)
from utils.data_processor import agregar_tudo, formata_brl
from utils.auth import perfil_admin

init_db()
migrar_db()

_admin = perfil_admin()

st.title("📋 Planejamento de Orçamentos e Prazos")
if not _admin:
    st.info("👁️ Modo somente leitura — edição desabilitada para este perfil.")

# ── 1. Projetos disponíveis ───────────────────────────────────────────────────
df_dashboard, _, _ = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum projeto encontrado. Importe as planilhas na página de Upload.")
    st.stop()

lista_cc         = sorted(df_dashboard["projeto"].unique().tolist())
mapeamento_nomes = dict(zip(df_dashboard["projeto"], df_dashboard["nome_projeto"]))

# ── 2. Detecta troca de CC e limpa TODOS os campos do formulário ──────────────
# Limpa qualquer chave de session_state relacionada ao formulário de orçamento.
# Isso garante que campos vazios também sejam limpos ao trocar de projeto.
def _limpar_form_state():
    prefixos = ("##", "orc_nome_", "orc_prev_")
    for chave in list(st.session_state.keys()):
        if any(chave.startswith(p) for p in prefixos):
            st.session_state.pop(chave, None)

if "orc_cc_anterior" not in st.session_state:
    st.session_state["orc_cc_anterior"] = None

cc_selecionado = st.selectbox(
    "Selecione o Centro de Custo (CC) do Projeto:",
    options=lista_cc,
    format_func=lambda x: f"{x} — {mapeamento_nomes.get(x, 'Sem Nome')}",
    key="orc_cc_atual",
)

if st.session_state["orc_cc_anterior"] != cc_selecionado:
    _limpar_form_state()
    st.session_state["orc_cc_anterior"] = cc_selecionado
    st.rerun()

# ── 3. Dados já salvos ────────────────────────────────────────────────────────
dados = carregar_orcamento_projeto(cc_selecionado)

def _parse_date_or_none(valor) -> date | None:
    if valor and str(valor) not in ("0", "None", "nan", ""):
        try:
            return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return None

def _str_or_none(d) -> str | None:
    return str(d) if d is not None else None

def _tem(chave: str) -> bool:
    return bool(dados and _parse_date_or_none(dados.get(chave)))

def _ind(chave: str) -> str:
    return "🔵 " if _tem(chave) else ""

orcamento_atual      = float(dados["orcamento_previsto"]) if dados and dados.get("orcamento_previsto") else 0.0
orc_tem_dado         = bool(dados and dados.get("orcamento_previsto") and float(dados["orcamento_previsto"]) > 0)
nome_editado_salvo   = (dados.get("nome_projeto_editado") or "") if dados else ""
nome_original        = mapeamento_nomes.get(cc_selecionado, "")

realizado_proj = 0.0
linha = df_dashboard[df_dashboard["projeto"] == cc_selecionado]
if not linha.empty:
    realizado_proj = float(linha.iloc[0].get("valor_total", 0))

# ── 4. Formulário principal ───────────────────────────────────────────────────
with st.form("form_orcamento", clear_on_submit=False):

    # ─ 3B: Edição do nome do projeto ─────────────────────────────────────────
    st.subheader("🏷️ Identificação do Projeto")
    nome_label = f"{'🔵 ' if nome_editado_salvo else ''}Nome do Projeto (editável):"
    v_nome = st.text_input(
        nome_label,
        value=nome_editado_salvo or nome_original,
        placeholder="Digite um nome personalizado (opcional)",
        disabled=not _admin,
        help="Se preenchido, substituirá o nome importado da planilha em todo o dashboard.",
    )

    st.divider()

    # ─ Orçamento ─────────────────────────────────────────────────────────────
    st.subheader("💰 Orçamento")
    col_fin1, col_fin2 = st.columns(2)
    with col_fin1:
        label_orc = f"{'🔵 ' if orc_tem_dado else ''}Orçamento previsto (R$):"
        v_orcamento = st.number_input(
            label_orc, min_value=0.0, value=orcamento_atual,
            format="%.2f", disabled=not _admin,
        )
    with col_fin2:
        st.text_input(
            "Orçamento realizado (R$) — somente leitura:",
            value=formata_brl(realizado_proj), disabled=True,
            help="Calculado automaticamente a partir dos lançamentos importados.",
        )

    st.divider()

    # ─ 3C: Cronograma (datas editáveis) ──────────────────────────────────────
    st.subheader("📅 Cronograma de Marcos")
    if _admin:
        st.caption("🔵 indica campo com dado já salvo — salvar irá atualizá-lo.")
    else:
        st.caption("🔵 indica campo com dado já salvo.")

    h1, h2, h3 = st.columns([2, 2, 2])
    h1.markdown("**Marco**")
    h2.markdown("**🗓️ Data Prevista**")
    h3.markdown("**✅ Data Realizada**")
    st.markdown("<hr style='margin:4px 0 12px 0'>", unsafe_allow_html=True)

    v = {k: _parse_date_or_none(dados.get(k)) if dados else None for k in [
        "data_inicio",
        "prev_viabilidade",      "real_viabilidade",
        "prev_qualidade",        "real_qualidade",
        "prev_aprov_lancamento", "real_aprov_lancamento",
        "prev_lancamento",       "real_lancamento",
    ]}

    r1c1, r1c2, r1c3 = st.columns([2, 2, 2])
    r1c1.markdown(f"**{_ind('data_inicio')}Início do Projeto**<br><small>(abertura CC)</small>", unsafe_allow_html=True)
    d_inicio = r1c2.date_input("##inicio_prev", value=v["data_inicio"], format="DD/MM/YYYY",
                                label_visibility="collapsed", disabled=not _admin)
    r1c3.markdown("<div style='padding-top:8px;color:#aaa;font-size:13px'>—</div>", unsafe_allow_html=True)

    r2c1, r2c2, r2c3 = st.columns([2, 2, 2])
    r2c1.markdown(f"**{_ind('prev_viabilidade')}Aprovação da Viabilidade**")
    p_viabilidade = r2c2.date_input("##viab_prev", value=v["prev_viabilidade"], format="DD/MM/YYYY",
                                     label_visibility="collapsed", disabled=not _admin)
    r_viabilidade = r2c3.date_input("##viab_real", value=v["real_viabilidade"], format="DD/MM/YYYY",
                                     label_visibility="collapsed", disabled=not _admin)

    r3c1, r3c2, r3c3 = st.columns([2, 2, 2])
    r3c1.markdown(f"**{_ind('prev_qualidade')}Critérios de Qualidade**")
    p_qualidade = r3c2.date_input("##qual_prev", value=v["prev_qualidade"], format="DD/MM/YYYY",
                                   label_visibility="collapsed", disabled=not _admin)
    r_qualidade = r3c3.date_input("##qual_real", value=v["real_qualidade"], format="DD/MM/YYYY",
                                   label_visibility="collapsed", disabled=not _admin)

    r4c1, r4c2, r4c3 = st.columns([2, 2, 2])
    r4c1.markdown(f"**{_ind('prev_aprov_lancamento')}Aprovação para Lançamento**")
    p_aprov_lanc = r4c2.date_input("##aprov_prev", value=v["prev_aprov_lancamento"], format="DD/MM/YYYY",
                                    label_visibility="collapsed", disabled=not _admin)
    r_aprov_lanc = r4c3.date_input("##aprov_real", value=v["real_aprov_lancamento"], format="DD/MM/YYYY",
                                    label_visibility="collapsed", disabled=not _admin)

    r5c1, r5c2, r5c3 = st.columns([2, 2, 2])
    r5c1.markdown(f"**{_ind('prev_lancamento')}🚀 LANÇAMENTO**")
    p_lancamento = r5c2.date_input("##lanc_prev", value=v["prev_lancamento"], format="DD/MM/YYYY",
                                    label_visibility="collapsed", disabled=not _admin)
    r_lancamento = r5c3.date_input("##lanc_real", value=v["real_lancamento"], format="DD/MM/YYYY",
                                    label_visibility="collapsed", disabled=not _admin)

    st.markdown("<br>", unsafe_allow_html=True)
    if _admin:
        botao_salvar = st.form_submit_button("💾 Salvar Dados do Projeto", type="primary")
    else:
        st.form_submit_button("💾 Salvar Dados do Projeto", type="primary", disabled=True)
        botao_salvar = False

# ── 5. Salvamento ─────────────────────────────────────────────────────────────
if botao_salvar and _admin:
    try:
        nome_para_salvar = v_nome.strip() if v_nome.strip() != nome_original.strip() else None
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
            nome_projeto_editado  = nome_para_salvar,
        )
        agregar_tudo.clear()
        st.success(f"✅ Dados do projeto **{cc_selecionado}** gravados com sucesso!")
        st.toast("Banco de dados atualizado!", icon="💾")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")

# ── 6. Resumo ─────────────────────────────────────────────────────────────────
st.divider()
nome_exibicao = nome_editado_salvo or nome_original
st.subheader(f"📊 Resumo — {cc_selecionado} / {nome_exibicao}")

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
            if diff > 0: return f"🔴 +{diff} dias"
            if diff < 0: return f"🟢 {abs(diff)} dias adiantado"
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
    df_marcos = pd.DataFrame([{
        "Marco":     nome, "Previsto": _fmt(prev),
        "Realizado": _fmt(real) if real is not None else "—",
        "Situação":  _delta(prev, real) if real is not None else "—",
    } for nome, prev, real in marcos])

    def _highlight(row):
        sit = row["Situação"]
        if "🔴" in str(sit): return ["","","background-color:rgba(220,38,38,.2)","background-color:rgba(220,38,38,.2);color:#f87171"]
        if "🟢" in str(sit): return ["","","background-color:rgba(22,163,74,.2)","background-color:rgba(22,163,74,.2);color:#4ade80"]
        if "✅" in str(sit): return ["","","background-color:rgba(37,99,235,.15)","background-color:rgba(37,99,235,.15);color:#93c5fd"]
        return ["","","",""]

    st.dataframe(df_marcos.style.apply(_highlight, axis=1), use_container_width=True, hide_index=True)

st.divider()

# ── 7. Previsões por Período (3D) ─────────────────────────────────────────────
st.subheader("📆 Previsões Orçamentárias por Período")
st.caption("Registre previsões de lançamento por ano ou semestre para este projeto.")

df_prev = carregar_previsoes_projeto(cc_selecionado)

if not df_prev.empty:
    df_exibe = df_prev[["id","periodo","tipo_periodo","descricao","valor","atualizado_em"]].copy()
    df_exibe.columns = ["ID","Período","Tipo","Descrição","Valor (R$)","Atualizado em"]
    st.dataframe(
        df_exibe.style.format({"Valor (R$)": "R$ {:,.2f}"}),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("Nenhuma previsão cadastrada para este projeto.")

if _admin:
    with st.expander("➕ Adicionar / Atualizar Previsão de Período"):
        with st.form("form_previsao", clear_on_submit=True):
            pc1, pc2, pc3 = st.columns(3)
            tipo_p  = pc1.selectbox("Tipo", ["anual", "semestral"], key="prev_tipo")
            periodo = pc2.text_input("Período", placeholder="Ex: 2026 ou 2026-S1", key="prev_periodo")
            valor_p = pc3.number_input("Valor (R$)", min_value=0.0, format="%.2f", key="prev_valor")
            desc_p  = st.text_input("Descrição / Fonte", placeholder='Ex: "Previsão do Neto"', key="prev_desc")
            if st.form_submit_button("💾 Salvar Previsão", type="primary"):
                if not periodo.strip():
                    st.error("Informe o período.")
                else:
                    salvar_previsao_periodo(
                        projeto=cc_selecionado, periodo=periodo.strip(),
                        valor=valor_p, tipo_periodo=tipo_p,
                        descricao=desc_p.strip() or None,
                    )
                    st.success(f"✅ Previsão '{periodo}' salva.")
                    st.rerun()

    if not df_prev.empty:
        with st.expander("🗑️ Remover Previsão"):
            opcoes_del = {
                f"{r['periodo']} ({r['tipo_periodo']}) — R$ {r['valor']:,.2f}": r["id"]
                for _, r in df_prev.iterrows()
            }
            sel_del = st.selectbox("Selecione para remover:", list(opcoes_del.keys()))
            if st.button("🗑️ Remover", type="secondary"):
                deletar_previsao_periodo(opcoes_del[sel_del])
                st.success("Previsão removida.")
                st.rerun()

st.divider()

# ── 8. Export / Import de dados de orçamento (3E) ────────────────────────────
st.subheader("📤 Exportar / Importar Dados de Orçamento")

col_exp, col_imp = st.columns(2)

with col_exp:
    st.markdown("**⬇️ Exportar todos os dados cadastrados**")
    df_orc_export = carregar_orcamentos()
    df_prev_export = carregar_previsoes_projeto(cc_selecionado) if not df_dashboard.empty else pd.DataFrame()

    # Gera Excel em memória com duas abas
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_orc_export.to_excel(writer, sheet_name="Orcamentos", index=False)
        if not df_prev_export.empty:
            df_prev_export.to_excel(writer, sheet_name="Previsoes", index=False)
    buf.seek(0)
    st.download_button(
        "⬇️ Baixar planilha de orçamentos (.xlsx)",
        data=buf,
        file_name="orcamentos_dashboard.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

with col_imp:
    st.markdown("**⬆️ Importar planilha de orçamentos**")
    if _admin:
        f_import = st.file_uploader(
            "Arquivo exportado anteriormente (.xlsx)",
            type=["xlsx"], key="import_orc",
        )
        if f_import and st.button("📥 Importar dados", type="primary", use_container_width=True):
            try:
                xl = pd.ExcelFile(io.BytesIO(f_import.read()))
                importados = 0
                if "Orcamentos" in xl.sheet_names:
                    df_imp_orc = xl.parse("Orcamentos")
                    for _, row in df_imp_orc.iterrows():
                        proj = str(row.get("projeto","")).strip()
                        if not proj: continue
                        salvar_orcamento(
                            projeto               = proj,
                            orcamento_previsto    = float(row.get("orcamento_previsto") or 0),
                            data_inicio           = str(row.get("data_inicio","")) or None,
                            prev_viabilidade      = str(row.get("prev_viabilidade","")) or None,
                            prev_qualidade        = str(row.get("prev_qualidade","")) or None,
                            prev_aprov_lancamento = str(row.get("prev_aprov_lancamento","")) or None,
                            prev_lancamento       = str(row.get("prev_lancamento","")) or None,
                            real_viabilidade      = str(row.get("real_viabilidade","")) or None,
                            real_qualidade        = str(row.get("real_qualidade","")) or None,
                            real_aprov_lancamento = str(row.get("real_aprov_lancamento","")) or None,
                            real_lancamento       = str(row.get("real_lancamento","")) or None,
                            nome_projeto_editado  = str(row.get("nome_projeto_editado","")) or None,
                        )
                        importados += 1
                if "Previsoes" in xl.sheet_names:
                    df_imp_prev = xl.parse("Previsoes")
                    for _, row in df_imp_prev.iterrows():
                        proj = str(row.get("projeto","")).strip()
                        if not proj: continue
                        salvar_previsao_periodo(
                            projeto      = proj,
                            periodo      = str(row.get("periodo","")).strip(),
                            valor        = float(row.get("valor") or 0),
                            tipo_periodo = str(row.get("tipo_periodo","anual")),
                            descricao    = str(row.get("descricao","")) or None,
                        )
                agregar_tudo.clear()
                st.success(f"✅ {importados} projetos importados com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro na importação: {e}")
    else:
        st.info("👁️ Importação disponível apenas para administradores.")

st.divider()

# ── 9. Excluir dados do projeto — só admin ────────────────────────────────────
if _admin:
    with st.expander("🗑️ Excluir todos os dados deste projeto"):
        nome_proj = nome_editado_salvo or nome_original
        st.warning(
            f"Esta ação remove **permanentemente todos os dados** do projeto "
            f"**{cc_selecionado} — {nome_proj}**, incluindo:\n\n"
            f"- 💰 Lançamentos de custos\n"
            f"- ⏱️ Registros de horas\n"
            f"- 📋 Orçamento, cronograma e previsões de período\n\n"
            f"Esta operação **não pode ser desfeita.**"
        )
        confirmacao = st.text_input(
            "Digite EXCLUIR para confirmar:",
            key="confirma_exclusao_projeto",
            placeholder="EXCLUIR",
        )
        if st.button(
            "🗑️ Excluir todos os dados do projeto",
            disabled=(confirmacao != "EXCLUIR"),
            type="secondary",
        ):
            resultado = deletar_projeto_completo(cc_selecionado)
            agregar_tudo.clear()
            _limpar_form_state()
            st.session_state.pop("confirma_exclusao_projeto", None)
            st.success(
                f"✅ Projeto **{cc_selecionado}** removido: "
                f"{resultado['custos']} lançamentos de custos, "
                f"{resultado['horas']} registros de horas, "
                f"{'orçamento e cronograma excluídos' if resultado['orcamento'] else 'sem orçamento cadastrado'}."
            )
            st.rerun()
else:
    if dados_atuais is None:
        st.info("Preencha o formulário acima e salve para ver o resumo.")
