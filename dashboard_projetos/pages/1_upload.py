import pages._pathfix  # garante sys.path antes de qualquer import
import streamlit as st
import pandas as pd
from utils.db import (
    init_db, salvar_custos, salvar_horas,
    listar_importacoes, deletar_importacao, limpar_tudo,
)
from utils.data_processor import (
    ler_planilha_bytes, preparar_custos, preparar_horas,
    validar_colunas, COLUNAS_CUSTOS, COLUNAS_HORAS, agregar_tudo,
)

init_db()

st.title("📤 Upload de Planilhas")
st.markdown(
    "Cada arquivo enviado é **acumulado** no histórico. "
    "Você pode enviar planilhas de meses diferentes sem perder dados anteriores."
)

with st.expander("📋 Ver formato esperado das planilhas"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Custos** (xlsx / csv)")
        st.dataframe(pd.DataFrame({
            "projeto":   ["Alpha", "Beta"],
            "categoria": ["Mão de obra", "Infra"],
            "valor":     [5000.00, 1200.00],
            "data":      ["2024-01-01", "2024-01-15"],
            "orcamento": [20000.00, 5000.00],
            "status":    ["Em andamento", "Em andamento"],
        }), hide_index=True, use_container_width=True)
    with c2:
        st.markdown("**Horas** (xlsx / csv)")
        st.dataframe(pd.DataFrame({
            "projeto":     ["Alpha", "Beta"],
            "colaborador": ["Ana Silva", "Carlos Souza"],
            "horas":       [80, 40],
            "data":        ["2024-01-01", "2024-01-10"],
            "tarefa":      ["Desenvolvimento", "Reunião"],
        }), hide_index=True, use_container_width=True)

st.divider()

col_l, col_r = st.columns(2)
with col_l:
    st.subheader("Planilha de Custos")
    f_custos = st.file_uploader("Arquivo de custos", type=["xlsx", "xls", "csv"], key="up_custos")
with col_r:
    st.subheader("Planilha de Horas")
    f_horas = st.file_uploader("Arquivo de horas", type=["xlsx", "xls", "csv"], key="up_horas")

st.divider()

if f_custos is not None or f_horas is not None:
    if st.button("💾 Importar e Salvar no Histórico", type="primary", use_container_width=True):
        avisos, sucessos = [], []

        if f_custos:
            bytes_c = f_custos.read()
            df_c = ler_planilha_bytes(bytes_c, f_custos.name)
            df_c = preparar_custos(df_c)
            erros_c = validar_colunas(df_c, COLUNAS_CUSTOS, "Custos")
            if erros_c:
                avisos += erros_c
            else:
                linhas, duplicado = salvar_custos(df_c, f_custos.name)
                if duplicado:
                    avisos.append(f"'{f_custos.name}' já foi importado antes — ignorado para evitar duplicação.")
                else:
                    sucessos.append(f"Custos: **{linhas} linhas** de `{f_custos.name}` salvas.")

        if f_horas:
            bytes_h = f_horas.read()
            df_h = ler_planilha_bytes(bytes_h, f_horas.name)
            df_h = preparar_horas(df_h)
            erros_h = validar_colunas(df_h, COLUNAS_HORAS, "Horas")
            if erros_h:
                avisos += erros_h
            else:
                linhas, duplicado = salvar_horas(df_h, f_horas.name)
                if duplicado:
                    avisos.append(f"'{f_horas.name}' já foi importado antes — ignorado para evitar duplicação.")
                else:
                    sucessos.append(f"Horas: **{linhas} linhas** de `{f_horas.name}` salvas.")

        for msg in sucessos:
            st.success(f"✅ {msg}")
        for msg in avisos:
            st.warning(f"⚠️ {msg}")

        if sucessos:
            agregar_tudo.clear()
            st.info("📊 Dashboard atualizado. Navegue para **Dashboard Financeiro**.")
else:
    st.info("⬆️ Selecione ao menos um arquivo para importar.")

st.divider()

st.subheader("📁 Histórico de Arquivos Importados")
df_imp = listar_importacoes()

if df_imp.empty:
    st.info("Nenhum arquivo importado ainda.")
else:
    exibe = df_imp.copy()
    exibe.columns = ["Tipo", "Arquivo", "Importado em", "Linhas"]
    exibe["Tipo"] = exibe["Tipo"].map({"custos": "💰 Custos", "horas": "⏱️ Horas"})
    st.dataframe(exibe, use_container_width=True, hide_index=True)

    st.markdown("**Remover um arquivo do histórico:**")
    opcoes = [f"{r['tipo']}|{r['arquivo']}" for _, r in df_imp.iterrows()]
    labels = [f"{r['tipo'].capitalize()} — {r['arquivo']}" for _, r in df_imp.iterrows()]
    idx = st.selectbox("Selecione", range(len(labels)), format_func=lambda i: labels[i], key="sel_del")
    if st.button("🗑️ Remover este arquivo", type="secondary"):
        tipo_sel, arq_sel = opcoes[idx].split("|", 1)
        removidas = deletar_importacao(arq_sel, tipo_sel)
        agregar_tudo.clear()
        st.success(f"✅ {removidas} linhas de `{arq_sel}` removidas.")
        st.rerun()

st.divider()

with st.expander("⚠️ Zona de perigo — apagar tudo"):
    st.warning("Esta ação remove **todos** os dados. Não pode ser desfeita.")
    confirmacao = st.text_input("Digite CONFIRMAR para habilitar o botão")
    if st.button("🔥 Apagar todos os dados", disabled=(confirmacao != "CONFIRMAR"), type="secondary"):
        limpar_tudo()
        agregar_tudo.clear()
        st.success("Banco de dados limpo.")
        st.rerun()
