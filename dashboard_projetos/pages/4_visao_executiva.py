import html
import sys
from pathlib import Path
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st
from utils.db import init_db
from utils.data_processor import (
    agregar_tudo, render_filtros_sidebar, calcular_risco_portfolio,
)
from utils.pdf_report import gerar_relatorio_risco_pdf

init_db()

st.title("🧭 Visão Executiva")
st.caption("Quais projetos precisam de atenção agora — risco combinado de custo e prazo.")

df_dashboard, df_custos_raw, _df_horas_raw = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

df_f = render_filtros_sidebar(df_dashboard, df_custos_raw)

if df_f.empty:
    st.info("Nenhum projeto encontrado para os filtros selecionados.")
    st.stop()

risco = calcular_risco_portfolio(df_f, df_custos_raw)

n_alto  = int((risco["nivel_risco"] == "alto").sum())
n_medio = int((risco["nivel_risco"] == "medio").sum())
n_baixo = int((risco["nivel_risco"] == "baixo").sum())

c1, c2, c3 = st.columns(3)
c1.metric("🔴 Alto risco", str(n_alto))
c2.metric("🟡 Risco médio", str(n_medio))
c3.metric("🟢 Baixo risco", str(n_baixo))

st.divider()

CORES_RISCO  = {"alto": "#7f1d1d", "medio": "#7c2d12", "baixo": "#14532d"}
ICONES_RISCO = {"alto": "🔴", "medio": "🟡", "baixo": "🟢"}
LABEL_RISCO  = {"alto": "Alto risco", "medio": "Risco médio", "baixo": "Baixo risco"}

destaque = risco[risco["nivel_risco"].isin(["alto", "medio"])]

if destaque.empty:
    st.success("✅ Nenhum projeto em risco alto ou médio nos filtros selecionados.")
else:
    for _, r in destaque.iterrows():
        cor    = CORES_RISCO[r["nivel_risco"]]
        icone  = ICONES_RISCO[r["nivel_risco"]]
        label  = LABEL_RISCO[r["nivel_risco"]]
        motivos_exibir = [m for m in r["motivos"] if not m.startswith("Projeção de custo")]
        pct_txt = (f"💰 Previsão de atingir {r['pct_projetado']:.0f}% do orçamento projetado"
                   if pd.notna(r["pct_projetado"]) else "💰 Previsão indisponível")
        atrasos_txt = [f"🔴 {m}" for m in motivos_exibir]
        if pd.notna(r["proxima_fase"]):
            fase_txt = f"🗓️ Próxima fase programada para {r['proxima_fase_data'].strftime('%d/%m/%Y')}"
        else:
            fase_txt = "🗓️ Todas as fases do cronograma já concluídas"
        linhas_corpo = [pct_txt, *atrasos_txt, fase_txt]
        corpo_html = "<br>".join(linhas_corpo)
        st.markdown(f"""
        <div style="background:{cor}22;border-left:4px solid {cor};border-radius:8px 8px 0 0;
                    padding:12px 16px">
            <div style="font-weight:700">{icone} {html.escape(str(r['nome_projeto']))} — {label}</div>
            <div style="opacity:.85;margin-top:4px;font-size:13px">{corpo_html}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button(
            "🔍 Ver detalhamento do projeto",
            key=f"ver_detalhe_{r['projeto']}",
            use_container_width=True,
        ):
            st.session_state["ir_para_projeto"] = r["projeto"]
            st.session_state["ir_para_tab"] = "🔍 Detalhamento"
            st.switch_page(str(_ROOT / "pages" / "3_projetos.py"))
        st.markdown("<div style='margin-bottom:10px'></div>", unsafe_allow_html=True)

baixo = risco[risco["nivel_risco"] == "baixo"]
if not baixo.empty:
    with st.expander(f"🟢 Ver {len(baixo)} projeto(s) em baixo risco"):
        for _, r in baixo.iterrows():
            st.markdown(f"- {r['nome_projeto']}")

st.divider()

col_csv, col_pdf = st.columns(2)

csv_export = risco.copy()
csv_export["motivos"] = csv_export["motivos"].apply(lambda m: "; ".join(m) if m else "")
col_csv.download_button(
    "⬇️ Exportar CSV",
    csv_export.to_csv(index=False).encode("utf-8"),
    "visao_executiva_riscos.csv",
    "text/csv",
    use_container_width=True,
)

filtros_aplicados = {
    "Projetos": st.session_state.get("filtro_projetos", []),
    "Ano": st.session_state.get("filtro_anos", []),
    "Mês": st.session_state.get("filtro_meses", []),
    "Status": st.session_state.get("filtro_status", []),
}
try:
    pdf_bytes = gerar_relatorio_risco_pdf(risco, filtros_aplicados)
    col_pdf.download_button(
        "📄 Exportar PDF",
        pdf_bytes,
        "visao_executiva_riscos.pdf",
        "application/pdf",
        use_container_width=True,
    )
except Exception as e:
    col_pdf.caption(f"PDF indisponível: {e}")
