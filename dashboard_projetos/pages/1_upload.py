import sys, os
from pathlib import Path
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from utils.db import (
    init_db, listar_importacoes, deletar_importacao, limpar_tudo,
)
from utils.data_processor import (
    processar_arquivo_custos, processar_arquivo_horas, agregar_tudo,
)
from utils.auth import perfil_admin

init_db()

# ── Controle de perfil ────────────────────────────────────────────────────────
_admin = perfil_admin()

st.title("📤 Upload de Planilhas")

if not _admin:
    st.info("👁️ Modo somente leitura — upload e alterações desabilitados para este perfil.")

st.markdown(
    "Cada arquivo enviado é **acumulado** no histórico. "
    "Você pode enviar planilhas de meses diferentes sem perder dados anteriores."
)

# ── Formato esperado ──────────────────────────────────────────────────────────
with st.expander("📋 Ver formato esperado das planilhas"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Planilha de Custos** (xlsx / csv)")
        st.dataframe(pd.DataFrame({
            "Data":                   ["01/01/2024 08:00:00"],
            "Ano":                    ["2024"],
            "Mês":                    ["Janeiro"],
            "Filial":                 ["SP01"],
            "Área":                   ["TI"],
            "Centro de Custo":        ["CC-1001 Projeto Alpha"],
            "Conta":                  ["4.1.01 Pessoal"],
            "Cód. Parceiro Negócio":  ["F-00123"],
            "Parceiro Negócio":       ["F-00123 Fornecedor X"],
            "Histórico":              ["NF 4521 Serviços"],
            "Realizado":              ["5.000,00"],
        }), hide_index=True, use_container_width=True)
    with c2:
        st.markdown("**Planilha de Horas** (xlsx / csv)")
        st.dataframe(pd.DataFrame({
            "Período":                              ["01/01/2024"],
            "C.Custo":                              ["1001"],
            "Ordem Interna":                        ["200001"],
            "Descrição Ordem Interna":              ["Projeto Alpha"],
            "Centro de Lucro":                      ["3001"],
            "Descrição C.Lucro":                    ["Software"],
            "Matricula":                            ["12345"],
            "Nome":                                 ["Ana Silva"],
            "CC Origem":                            ["5001"],
            "Descrição CC Origem":                  ["Dev Backend"],
            "Hs Nor":                               ["8"],
            "Tipo de Projeto":                      ["Interno"],
            "Cód Produto":                          ["P-001"],
            "Descrição Produto":                    ["Sistema X"],
            "CATEGORIA":                            ["Desenvolvimento"],
            "ATIVIDADE":                            ["Codificação"],
            "DETALHES":                             ["API REST"],
            "C.Custo - Descrição Ordem Interna":    ["1001 - Projeto Alpha"],
            "Matricula - Nome":                     ["12345 - Ana Silva"],
            "Segmento":                             ["Enterprise"],
        }), hide_index=True, use_container_width=True)
    st.info(
        "💡 A coluna **Centro de Custo** (custos) e **C.Custo** (horas) são usadas "
        "como chave de projeto para cruzar as duas planilhas."
    )

st.divider()

# ── Uploaders — desabilitados para visualizador ───────────────────────────────
col_l, col_r = st.columns(2)
with col_l:
    st.subheader("Planilha de Custos")
    arquivos_custos = st.file_uploader(
        "Arquivo(s) de custos", type=["xlsx", "xls", "csv"], key="up_custos",
        disabled=not _admin, accept_multiple_files=True,
    )
with col_r:
    st.subheader("Planilha de Horas")
    arquivos_horas = st.file_uploader(
        "Arquivo(s) de horas", type=["xlsx", "xls", "csv"], key="up_horas",
        disabled=not _admin, accept_multiple_files=True,
    )

st.divider()

# ── Processar — só admin ──────────────────────────────────────────────────────
if _admin:
    if arquivos_custos or arquivos_horas:
        if st.button("💾 Importar e Salvar no Histórico", type="primary", use_container_width=True):
            avisos, sucessos = [], []

            for arquivo in arquivos_custos:
                resultado = processar_arquivo_custos(arquivo)
                if resultado["ok"]:
                    sucessos.append(resultado["mensagem"])
                else:
                    avisos.append(resultado["mensagem"])
                    if resultado["colunas"] is not None:
                        with st.expander(f"🔍 Colunas detectadas em `{arquivo.name}`"):
                            st.write(resultado["colunas"])

            for arquivo in arquivos_horas:
                resultado = processar_arquivo_horas(arquivo)
                if resultado["ok"]:
                    sucessos.append(resultado["mensagem"])
                else:
                    avisos.append(resultado["mensagem"])
                    if resultado["colunas"] is not None:
                        with st.expander(f"🔍 Colunas detectadas em `{arquivo.name}`"):
                            st.write(resultado["colunas"])

            for msg in sucessos: st.success(f"✅ {msg}")
            for msg in avisos:   st.warning(f"⚠️ {msg}")

            if sucessos:
                agregar_tudo.clear()
                st.info("📊 Dashboard atualizado. Navegue para **Dashboard Financeiro**.")
    else:
        st.info("⬆️ Selecione ao menos um arquivo para importar.")

st.divider()

# ── Histórico ─────────────────────────────────────────────────────────────────
st.subheader("📁 Histórico de Arquivos Importados")
df_imp = listar_importacoes()

if df_imp.empty:
    st.info("Nenhum arquivo importado ainda.")
else:
    exibe = df_imp.copy()
    exibe.columns = ["Tipo", "Arquivo", "Importado em", "Linhas"]
    exibe["Tipo"] = exibe["Tipo"].map({"custos": "💰 Custos", "horas": "⏱️ Horas"})
    st.dataframe(exibe, use_container_width=True, hide_index=True)

    # Remoção — só admin
    if _admin:
        st.markdown("**Remover um arquivo do histórico:**")
        opcoes = [f"{r['tipo']}|{r['arquivo']}" for _, r in df_imp.iterrows()]
        labels = [f"{r['tipo'].capitalize()} — {r['arquivo']}" for _, r in df_imp.iterrows()]
        idx = st.selectbox("Selecione", range(len(labels)),
                           format_func=lambda i: labels[i], key="sel_del")
        if st.button("🗑️ Remover este arquivo", type="secondary"):
            tipo_sel, arq_sel = opcoes[idx].split("|", 1)
            removidas = deletar_importacao(arq_sel, tipo_sel)
            agregar_tudo.clear()
            st.success(f"✅ {removidas} linhas de `{arq_sel}` removidas.")
            st.rerun()

st.divider()

# ── Zona de perigo — só admin ─────────────────────────────────────────────────
if _admin:
    with st.expander("⚠️ Zona de perigo — apagar tudo"):
        st.warning("Esta ação remove **todos** os dados. Não pode ser desfeita.")

        def _callback_apagar():
            limpar_tudo()
            agregar_tudo.clear()
            st.session_state["texto_confirmacao"] = ""
            st.toast("Banco de dados limpo com sucesso!", icon="🔥")

        if "texto_confirmacao" not in st.session_state:
            st.session_state.texto_confirmacao = ""

        confirmacao = st.text_input(
            "Digite CONFIRMAR para habilitar o botão",
            key="texto_confirmacao",
        )
        if st.button(
            "🔥 Apagar todos os dados",
            disabled=(confirmacao != "CONFIRMAR"),
            type="secondary",
            on_click=_callback_apagar,
        ):
            st.rerun()
