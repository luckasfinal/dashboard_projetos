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
    STATUS_OPCOES, STATUS_DEFAULT,
)
from utils.data_processor import (
    agregar_tudo, formata_brl, badge_status_projeto, importar_orcamento_de_excel,
)
from utils.auth import perfil_admin

init_db()
migrar_db()

_admin = perfil_admin()

st.title("📋 Planejamento de Orçamentos e Prazos")
if not _admin:
    st.info(
        "👁️ **Modo de leitura.** Veja abaixo o resumo, o cronograma e as previsões "
        "de cada projeto. Para editar, entre como administrador em **Alterar usuário** (barra lateral)."
    )
    # Oculta o formulário de edição (renderizado desabilitado) — visão limpa de leitura.
    # O resumo, cronograma e previsões abaixo permanecem visíveis.
    st.markdown("""
    <style>
    /* Esconde o formulário de orçamento no modo visualizador */
    div[data-testid="stForm"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

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

# ── Proteção contra exclusão de dados já preenchidos ──────────────────────────
# Se o usuário deixar um campo em branco que já tinha valor salvo, o valor
# anterior é preservado e o usuário é avisado.

def _protege_texto(novo: str, antigo: str) -> tuple[str, bool]:
    antigo_str = (antigo or "").strip()
    novo_str   = (novo or "").strip()
    if novo_str == "" and antigo_str not in ("", "0", "None", "nan"):
        return antigo_str, True
    return novo_str, False

def _protege_data(novo_date, antigo_str) -> tuple[str | None, bool]:
    novo_str      = _str_or_none(novo_date)
    antigo_valido = antigo_str and str(antigo_str) not in ("0", "None", "nan", "")
    if novo_str is None and antigo_valido:
        return str(antigo_str), True
    return novo_str, False

def _protege_numero(novo: float, antigo: float) -> tuple[float, bool]:
    if novo == 0 and antigo and antigo > 0:
        return antigo, True
    return novo, False

orcamento_atual      = float(dados["orcamento_previsto"]) if dados and dados.get("orcamento_previsto") else 0.0
orc_tem_dado         = bool(dados and dados.get("orcamento_previsto") and float(dados["orcamento_previsto"]) > 0)
nome_editado_salvo   = (dados.get("nome_projeto_editado") or "") if dados else ""
nome_original        = mapeamento_nomes.get(cc_selecionado, "")
status_salvo         = (dados.get("status_projeto") or STATUS_DEFAULT) if dados else STATUS_DEFAULT

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

    status_index = STATUS_OPCOES.index(status_salvo) if status_salvo in STATUS_OPCOES else 0
    v_status = st.selectbox(
        "📌 Status do Projeto:",
        options=STATUS_OPCOES,
        index=status_index,
        disabled=not _admin,
        help="Etapa atual do projeto no fluxo de aprovação/lançamento.",
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
        campos_protegidos = []

        # Nome do projeto: não permite limpar um nome editado já salvo
        v_nome_strip = v_nome.strip()
        if v_nome_strip == "" and nome_editado_salvo.strip() != "":
            nome_para_salvar = nome_editado_salvo
            campos_protegidos.append("Nome do Projeto")
        elif v_nome_strip == nome_original.strip():
            nome_para_salvar = None
        else:
            nome_para_salvar = v_nome_strip

        # Orçamento previsto: não permite zerar um valor já preenchido
        v_orcamento_final, prot = _protege_numero(v_orcamento, orcamento_atual)
        if prot: campos_protegidos.append("Orçamento previsto")

        # Datas do cronograma: não permite apagar datas já salvas
        data_inicio_f,      p1 = _protege_data(d_inicio,      dados.get("data_inicio")           if dados else None)
        prev_viab_f,        p2 = _protege_data(p_viabilidade, dados.get("prev_viabilidade")      if dados else None)
        real_viab_f,        p3 = _protege_data(r_viabilidade, dados.get("real_viabilidade")      if dados else None)
        prev_qual_f,        p4 = _protege_data(p_qualidade,   dados.get("prev_qualidade")        if dados else None)
        real_qual_f,        p5 = _protege_data(r_qualidade,   dados.get("real_qualidade")        if dados else None)
        prev_aprov_f,       p6 = _protege_data(p_aprov_lanc,  dados.get("prev_aprov_lancamento") if dados else None)
        real_aprov_f,       p7 = _protege_data(r_aprov_lanc,  dados.get("real_aprov_lancamento") if dados else None)
        prev_lanc_f,        p8 = _protege_data(p_lancamento,  dados.get("prev_lancamento")        if dados else None)
        real_lanc_f,        p9 = _protege_data(r_lancamento,  dados.get("real_lancamento")        if dados else None)

        nomes_marcos = {
            "p1": "Início do Projeto", "p2": "Prev. Viabilidade", "p3": "Real. Viabilidade",
            "p4": "Prev. Qualidade",   "p5": "Real. Qualidade",
            "p6": "Prev. Aprov. Lançamento", "p7": "Real. Aprov. Lançamento",
            "p8": "Prev. Lançamento", "p9": "Real. Lançamento",
        }
        for var_nome, protegido in [("p1",p1),("p2",p2),("p3",p3),("p4",p4),("p5",p5),("p6",p6),("p7",p7),("p8",p8),("p9",p9)]:
            if protegido:
                campos_protegidos.append(nomes_marcos[var_nome])

        salvar_orcamento(
            projeto               = cc_selecionado,
            orcamento_previsto    = v_orcamento_final,
            status_projeto        = v_status,
            data_inicio           = data_inicio_f,
            prev_viabilidade      = prev_viab_f,
            prev_qualidade        = prev_qual_f,
            prev_aprov_lancamento = prev_aprov_f,
            prev_lancamento       = prev_lanc_f,
            real_viabilidade      = real_viab_f,
            real_qualidade        = real_qual_f,
            real_aprov_lancamento = real_aprov_f,
            real_lancamento       = real_lanc_f,
            nome_projeto_editado  = nome_para_salvar,
        )
        agregar_tudo.clear()
        st.success(f"✅ Dados do projeto **{cc_selecionado}** gravados com sucesso!")
        if campos_protegidos:
            st.warning(
                "⚠️ Os seguintes campos já possuíam dados e não podem ser deixados em branco — "
                "os valores anteriores foram mantidos: " + ", ".join(campos_protegidos)
            )
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

    status_atual = dados_atuais.get("status_projeto") or STATUS_DEFAULT
    st.markdown(
        f"<div style='margin-bottom:10px'>Status atual: {badge_status_projeto(status_atual)}</div>",
        unsafe_allow_html=True,
    )

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
    st.markdown("**⬆️ Importar planilha(s) de orçamentos**")
    if _admin:
        arquivos_import = st.file_uploader(
            "Arquivo(s) exportado(s) anteriormente (.xlsx)",
            type=["xlsx"], key="import_orc", accept_multiple_files=True,
        )
        if arquivos_import and st.button("📥 Importar dados", type="primary", use_container_width=True):
            try:
                importados = sum(
                    importar_orcamento_de_excel(f_import.read())
                    for f_import in arquivos_import
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
