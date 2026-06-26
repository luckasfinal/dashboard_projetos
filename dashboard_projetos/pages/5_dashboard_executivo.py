import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st
from utils.db import init_db
from utils.data_processor import (
    agregar_tudo, render_filtros_sidebar, formata_brl_curto,
)
from utils.dashboard_executivo import (
    calcular_marcos, calcular_resumo_executivo, calcular_status_projetos,
    calcular_recursos, calcular_burn_rate,
    calcular_forecast_prazo, calcular_forecast_custo, calcular_matriz_prazo_custo,
)
from utils import charts
from utils.pdf_report import gerar_relatorio_executivo_pdf

init_db()

st.title("📋 Dashboard Executivo de Projetos")
st.caption("Visão consolidada de prazo, custo, recursos e previsões.")

df_dashboard, df_custos_raw, df_horas_raw = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

df_f = render_filtros_sidebar(df_dashboard, df_custos_raw)

projetos_f = df_f["projeto"].unique()

df_custos_f = (
    df_custos_raw[df_custos_raw["centro_de_custo"].isin(projetos_f)].copy()
    if not df_custos_raw.empty else pd.DataFrame()
)
df_horas_f = (
    df_horas_raw[df_horas_raw["c_custo"].isin(projetos_f)].copy()
    if not df_horas_raw.empty else pd.DataFrame()
)

with st.sidebar:
    st.divider()
    st.subheader("🔍 Filtros desta página")
    contas_disp = (
        sorted(df_custos_f["conta"].dropna().unique().tolist())
        if not df_custos_f.empty and "conta" in df_custos_f.columns else []
    )
    conta_sel = st.multiselect(
        "Conta Contábil:",
        options=contas_disp,
        default=[],
        key="exec_filtro_categoria_custo",
    )
    colabs = (
        sorted(df_horas_f["nome"].dropna().unique().tolist())
        if not df_horas_f.empty and "nome" in df_horas_f.columns else []
    )
    colab_sel = st.multiselect("Colaborador:", options=colabs, default=[], key="exec_filtro_colaborador")

if df_f.empty:
    st.info("Nenhum projeto encontrado para os filtros selecionados.")
    st.stop()

if conta_sel and not df_custos_f.empty:
    df_custos_f = df_custos_f[df_custos_f["conta"].isin(conta_sel)]

if colab_sel and not df_horas_f.empty:
    df_horas_f = df_horas_f[df_horas_f["nome"].isin(colab_sel)]

# ── Pre-compute ──────────────────────────────────────────────────────────────
df_marcos = calcular_marcos(df_f)
resumo    = calcular_resumo_executivo(df_f, df_custos_f, df_horas_f, df_marcos)
df_status = calcular_status_projetos(df_f, df_marcos, df_custos_f, df_horas_f)
df_fp     = calcular_forecast_prazo(df_f, df_marcos)
df_fc     = calcular_forecast_custo(df_f, df_marcos)
df_matriz = calcular_matriz_prazo_custo(df_fp, df_fc)

if not df_custos_f.empty and "mes_ref" in df_custos_f.columns:
    df_br = calcular_burn_rate(df_custos_f)
    if not df_br.empty:
        _nomes_br = df_f[["projeto", "nome_projeto"]].drop_duplicates()
        df_br = df_br.merge(_nomes_br, on="projeto", how="left")
else:
    df_br = pd.DataFrame()

if not df_custos_f.empty and "conta" in df_custos_f.columns and "centro_de_custo" in df_custos_f.columns:
    nomes_proj = df_f[["projeto", "nome_projeto"]].drop_duplicates()
    df_cat = (
        df_custos_f.groupby(["centro_de_custo", "conta"])["realizado"].sum()
        .reset_index().rename(columns={"centro_de_custo": "projeto", "realizado": "total_custo"})
        .merge(nomes_proj, on="projeto", how="left")
    )
else:
    df_cat = pd.DataFrame(columns=["projeto", "conta", "total_custo", "nome_projeto"])

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_resumo, tab_prazo, tab_custos, tab_estrategico, tab_pdf = st.tabs([
    "📊 Resumo", "📅 Prazo & Marcos", "💰 Custos & Recursos", "🎯 Estratégico", "📄 Exportar PDF",
])

# ── TAB 1: RESUMO ─────────────────────────────────────────────────────────────
with tab_resumo:
    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)
    c1.metric("📁 Projetos Ativos",   resumo["projetos_ativos"])
    c2.metric("⚠️ Com Atraso",        resumo["projetos_com_atraso"])
    c3.metric("⏱️ Horas Consumidas",  f"{resumo['horas_consumidas']:,.0f} h")
    c4.metric("💰 Custos Acumulados", formata_brl_curto(resumo["custos_acumulados"]))
    c5.metric("✅ % Médio Conclusão", f"{resumo['pct_medio_conclusao']*100:.1f}%")
    c6.metric("📅 Atraso Médio",      f"{resumo['prazo_medio_atraso']:.0f} dias")

    st.divider()
    st.subheader("Status Geral dos Projetos")
    busca = st.text_input("🔎 Buscar projeto:", key="exec_busca_projeto")
    df_status_disp = df_status.copy()
    if busca:
        df_status_disp = df_status_disp[
            df_status_disp["nome_projeto"].str.contains(busca, case=False, na=False)
        ]
    colunas_exib = {
        "status_visual": "", "nome_projeto": "Projeto",
        "pct_concluido": "% Concluído", "marcos_concluidos": "Marcos Conc.",
        "marcos_totais": "Marcos Tot.", "atraso_medio_dias": "Atraso Médio (d)",
        "horas_total": "Horas", "custo_total": "Custo",
    }
    if "status_projeto" in df_status_disp.columns:
        colunas_exib["status_projeto"] = "Status"
    df_disp = df_status_disp[[c for c in colunas_exib if c in df_status_disp.columns]].copy()
    df_disp = df_disp.rename(columns=colunas_exib)
    df_disp["% Concluído"] = (df_disp["% Concluído"] * 100).round(1)
    st.dataframe(
        df_disp,
        use_container_width=True,
        column_config={
            "% Concluído": st.column_config.ProgressColumn(
                format="%.0f%%", min_value=0, max_value=100
            ),
            "Custo": st.column_config.NumberColumn(format="R$ %.0f"),
            "Horas": st.column_config.NumberColumn(format="%.0f h"),
        },
    )

# ── TAB 2: PRAZO & MARCOS ─────────────────────────────────────────────────────
with tab_prazo:
    st.subheader("Evolução Física dos Projetos")
    st.plotly_chart(charts.grafico_evolucao_fisica(df_status), use_container_width=True)

    with st.expander("🔍 Ver marcos de um projeto"):
        proj_nome = st.selectbox("Projeto:", df_f["nome_projeto"].unique(), key="exec_proj_drill")
        if proj_nome:
            proj_id = df_f[df_f["nome_projeto"] == proj_nome]["projeto"].iloc[0]
            drill_cols = ["marco", "data_prevista", "data_realizada", "desvio_dias", "status_marco"]
            rename_drill = {
                "marco": "Marco", "data_prevista": "Previsto",
                "data_realizada": "Realizado", "desvio_dias": "Desvio (d)",
                "status_marco": "Status",
            }
            if "observacao" in df_marcos.columns:
                drill_cols.append("observacao")
                rename_drill["observacao"] = "Observação"
            st.dataframe(
                df_marcos[df_marcos["projeto"] == proj_id][drill_cols].rename(columns=rename_drill),
                use_container_width=True,
            )

    st.divider()
    st.subheader("Análise de Marcos")
    total_m     = len(df_marcos)
    atrasados_m = int((df_marcos["status_marco"] == "Atrasado").sum())
    pct_atr     = atrasados_m / total_m * 100 if total_m > 0 else 0
    ma1, ma2, ma3 = st.columns(3)
    ma1.metric("Total de Marcos",   total_m)
    ma2.metric("Marcos Atrasados",  atrasados_m)
    ma3.metric("% Atrasados",       f"{pct_atr:.1f}%")
    df_marcos_disp = df_marcos[df_marcos["data_prevista"].notna()].copy()
    analise_cols = ["nome_projeto", "marco", "data_prevista", "data_realizada", "desvio_dias", "status_marco"]
    rename_analise = {
        "nome_projeto": "Projeto", "marco": "Marco",
        "data_prevista": "Previsto", "data_realizada": "Realizado",
        "desvio_dias": "Desvio (d)", "status_marco": "Status",
    }
    if "observacao" in df_marcos_disp.columns:
        analise_cols.append("observacao")
        rename_analise["observacao"] = "Observação"
    st.dataframe(
        df_marcos_disp[analise_cols].rename(columns=rename_analise),
        use_container_width=True,
    )

    st.divider()
    st.subheader("Forecast de Prazo")
    st.dataframe(
        df_fp.rename(columns={
            "nome_projeto": "Projeto", "data_planejada": "Data Planejada",
            "atraso_medio_dias": "Atraso Médio (d)", "forecast": "Forecast",
            "desvio_total": "Desvio (d)",
        }),
        use_container_width=True,
    )

# ── TAB 3: CUSTOS & RECURSOS ──────────────────────────────────────────────────
with tab_custos:
    if df_cat.empty:
        st.info("Sem dados de custo para os filtros selecionados.")
    else:
        st.plotly_chart(charts.grafico_custos_empilhados(df_cat), use_container_width=True)
        st.plotly_chart(charts.grafico_distribuicao_custos(df_cat), use_container_width=True)

    st.divider()
    st.subheader("Burn Rate")
    if not df_br.empty:
        st.plotly_chart(charts.grafico_burn_rate_temporal(df_br), use_container_width=True)
    else:
        st.info("Sem dados de custo mensais para exibir burn rate.")

    st.divider()
    st.subheader("Consumo de Recursos")
    df_rec = calcular_recursos(df_f, df_horas_f)
    if df_rec.empty:
        st.info("Sem dados de horas para os filtros selecionados.")
    else:
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("**🏆 Top 5 — Projetos por horas**")
            for _, row in df_rec.nlargest(5, "horas_total").iterrows():
                nm = row.get("nome_projeto") or row.get("projeto", "—")
                st.markdown(f"- {nm}: **{row['horas_total']:.0f} h**")
        with r2:
            st.markdown("**🏆 Top 5 — Colaboradores por horas**")
            if not df_horas_f.empty:
                top_c = df_horas_f.groupby("nome")["hs_nor"].sum().nlargest(5).reset_index()
                for _, row in top_c.iterrows():
                    st.markdown(f"- {row['nome']}: **{row['hs_nor']:.0f} h**")

    st.divider()
    st.subheader("Forecast de Custo (EAC)")
    df_fc_disp = df_fc.rename(columns={
        "nome_projeto":   "Projeto",
        "custo_atual":    "Custo Atual",
        "pct_concluido":  "% Concluído",
        "eac":            "EAC",
        "orcamento":      "Orçamento",
        "desvio_eac_pct": "Desvio EAC (%)",
        "cpi":            "CPI",
    }).copy()
    df_fc_disp["% Concluído"] = (df_fc_disp["% Concluído"] * 100).round(1)
    st.dataframe(
        df_fc_disp,
        use_container_width=True,
        column_config={
            "Custo Atual":    st.column_config.NumberColumn(format="R$ %.0f"),
            "EAC":            st.column_config.NumberColumn(format="R$ %.0f"),
            "Orçamento":      st.column_config.NumberColumn(format="R$ %.0f"),
            "% Concluído":    st.column_config.ProgressColumn(
                format="%.0f%%", min_value=0, max_value=100
            ),
            "Desvio EAC (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "CPI":            st.column_config.NumberColumn(format="%.2f"),
        },
    )
    st.caption(
        "**CPI (Cost Performance Index):** "
        "> 1,00 = eficiente (gasta menos que o planejado) · "
        "= 1,00 = exatamente no orçamento · "
        "< 1,00 = em risco de custo"
    )

# ── TAB 4: ESTRATÉGICO ────────────────────────────────────────────────────────
with tab_estrategico:
    if df_matriz.empty:
        st.info("Dados insuficientes para a matriz. Cadastre orçamentos e marcos nos projetos.")
    else:
        st.plotly_chart(charts.grafico_matriz_executiva(df_matriz), use_container_width=True)
        st.divider()
        st.subheader("Resumo de Riscos por Projeto")
        st.caption(
            "**Desvio de Prazo (d):** dias entre o lançamento previsto e o forecast "
            "(baseado no atraso médio dos marcos concluídos; positivo = atraso).  \n"
            "**Desvio de Custo (%):** diferença entre o EAC (estimativa de custo ao término, "
            "calculada como custo atual ÷ % concluído) e o orçamento aprovado "
            "(positivo = acima do orçamento)."
        )
        df_risco = df_matriz[["nome_projeto", "desvio_prazo_dias", "desvio_eac_pct", "quadrante"]].rename(
            columns={
                "nome_projeto": "Projeto",
                "desvio_prazo_dias": "Desvio Prazo (d)",
                "desvio_eac_pct": "Desvio Custo (%)",
                "quadrante": "Quadrante",
            }
        )
        st.dataframe(
            df_risco,
            use_container_width=True,
            column_config={
                "Desvio Prazo (d)": st.column_config.NumberColumn(format="%.0f d"),
                "Desvio Custo (%)": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

# ── TAB 5: EXPORTAR PDF ───────────────────────────────────────────────────────
with tab_pdf:
    st.subheader("Exportar Relatório em PDF")
    st.markdown(
        "O relatório inclui todos os dados das demais abas:\n\n"
        "- **Resumo Executivo** — KPIs e status geral dos projetos\n"
        "- **Prazo & Marcos** — análise de marcos e forecast de prazo\n"
        "- **Custos & Recursos** — distribuição por conta contábil, burn rate e forecast EAC\n"
        "- **Estratégico** — matriz prazo × custo com classificação de quadrante"
    )
    st.divider()
    try:
        filtros_pdf = {
            "Projetos": list(st.session_state.get("filtro_projetos", []) or []),
            "Anos":     list(st.session_state.get("filtro_anos", []) or []),
            "Status":   list(st.session_state.get("filtro_status", []) or []),
        }
        pdf_bytes = gerar_relatorio_executivo_pdf(
            resumo=resumo,
            df_status=df_status,
            df_marcos=df_marcos,
            df_fp=df_fp,
            df_cat=df_cat,
            df_fc=df_fc,
            df_matriz=df_matriz,
            df_br=df_br,
            filtros=filtros_pdf,
        )
        nome_arq = f"dashboard_executivo_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        st.download_button(
            "📥 Baixar PDF",
            pdf_bytes,
            nome_arq,
            "application/pdf",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Erro ao gerar PDF: {e}")
