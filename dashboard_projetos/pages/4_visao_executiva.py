import html
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from utils.db import init_db
from utils.data_processor import (
    agregar_tudo, render_filtros_sidebar, calcular_risco_portfolio,
)
from utils.dashboard_executivo import calcular_marcos
from utils.pdf_report import gerar_relatorio_risco_pdf

init_db()

st.title("🧭 Visão Executiva")
st.caption("Risco combinado de custo e prazo — todos os projetos num relance.")

df_dashboard, df_custos_raw, _df_horas_raw = agregar_tudo()

if df_dashboard.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

df_f = render_filtros_sidebar(df_dashboard, df_custos_raw)

if df_f.empty:
    st.info("Nenhum projeto encontrado para os filtros selecionados.")
    st.stop()

risco = calcular_risco_portfolio(df_f, df_custos_raw)
df_marcos_ve = calcular_marcos(df_f)

# ── 1. KPIs ───────────────────────────────────────────────────────────────────
n_alto  = int((risco["nivel_risco"] == "alto").sum())
n_medio = int((risco["nivel_risco"] == "medio").sum())
n_baixo = int((risco["nivel_risco"] == "baixo").sum())

c1, c2, c3 = st.columns(3)
c1.metric("🔴 Alto risco",  str(n_alto))
c2.metric("🟡 Risco médio", str(n_medio))
c3.metric("🟢 Baixo risco", str(n_baixo))

st.divider()

# ── 2. Mapa de Risco — scatter com etiquetas ──────────────────────────────────
st.subheader("📊 Mapa de Risco — Custo × Prazo")
st.caption("Tamanho da bolha = orçamento previsto. Canto superior direito = zona crítica.")

_COR   = {"Alto": "#ef4444", "Médio": "#f59e0b", "Baixo": "#22c55e"}
_LABEL = {"alto": "Alto",    "medio": "Médio",   "baixo": "Baixo"}

rp = risco.copy()
rp["nivel_label"]   = rp["nivel_risco"].map(_LABEL)
rp["pct_plot"]      = rp["pct_projetado"].fillna(0)
rp["orc_plot"]      = rp["orcamento"].clip(lower=1_000)
rp["realizado_fmt"] = rp["realizado"].apply(lambda v: f"R$ {v:,.0f}")
rp["orcamento_fmt"] = rp["orcamento"].apply(lambda v: f"R$ {v:,.0f}" if v > 0 else "—")
rp["etiqueta"]      = rp["nome_projeto"].apply(lambda n: n[:16] + "…" if len(n) > 16 else n)

fig_scatter = go.Figure()
for nivel_label, grp in rp.groupby("nivel_label"):
    tamanhos = grp["orc_plot"].apply(lambda v: max(12, min(50, v / 50_000)))
    # Etiquetas visíveis apenas no Alto risco (evita sobreposição)
    # Baixo risco oculto por padrão, disponível via legenda
    show_text = nivel_label == "Alto"
    fig_scatter.add_trace(go.Scatter(
        x=grp["pct_plot"],
        y=grp["dias_atraso_max"],
        mode="markers+text" if show_text else "markers",
        name=nivel_label,
        visible=True if nivel_label != "Baixo" else "legendonly",
        marker=dict(
            size=tamanhos,
            color=_COR.get(nivel_label, "#94a3b8"),
            opacity=0.85,
            line=dict(width=1, color="rgba(255,255,255,0.2)"),
        ),
        text=grp["etiqueta"] if show_text else None,
        textposition="top center",
        textfont=dict(size=9, color="rgba(255,255,255,0.85)"),
        customdata=grp[["realizado_fmt", "orcamento_fmt", "nome_projeto"]].values,
        hovertemplate=(
            "<b>%{customdata[2]}</b><br>"
            "Custo projetado: %{x:.0f}% do orçamento<br>"
            "Atraso: %{y} dias<br>"
            "Realizado: %{customdata[0]}<br>"
            "Orçamento: %{customdata[1]}"
            "<extra></extra>"
        ),
    ))

fig_scatter.add_vline(
    x=100, line_dash="dash", line_color="rgba(239,68,68,0.5)",
    annotation_text="100% orçamento",
    annotation_font_color="#ef4444",
    annotation_position="top right",
)
fig_scatter.update_layout(
    template="plotly_dark",
    height=460,
    margin=dict(t=30, b=40, l=60, r=20),
    xaxis_title="% do orçamento projetado",
    yaxis_title="Dias de atraso em marcos",
    legend=dict(title="Risco", orientation="h", yanchor="bottom", y=1.01, x=0),
    hovermode="closest",
)
st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# ── 3. Cards expansíveis por projeto ─────────────────────────────────────────
_ICONE      = {"alto": "🔴", "medio": "🟡", "baixo": "🟢"}
_LABEL_CARD = {"alto": "Alto risco", "medio": "Risco médio"}

destaque = risco[risco["nivel_risco"].isin(["alto", "medio"])]
baixo    = risco[risco["nivel_risco"] == "baixo"]

if destaque.empty:
    st.success("✅ Nenhum projeto em risco alto ou médio nos filtros selecionados.")
else:
    for _, r in destaque.iterrows():
        pct_s  = f"{r['pct_projetado']:.0f}% do orçamento" if pd.notna(r["pct_projetado"]) else "s/orçamento"
        atr_s  = f"{r['dias_atraso_max']}d de atraso" if r["dias_atraso_max"] > 0 else "No prazo"
        fase_s = (f"🗓️ {r['proxima_fase']} em {r['proxima_fase_data'].strftime('%d/%m/%Y')}"
                  if pd.notna(r["proxima_fase"]) else "🏁 Todas as fases concluídas")

        with st.expander(
            f"{_ICONE[r['nivel_risco']]} **{html.escape(str(r['nome_projeto']))}**"
            f" — {_LABEL_CARD[r['nivel_risco']]}"
        ):
            # Indicadores distribuídos em 3 colunas iguais
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"💰 **{pct_s}**")
            col2.markdown(f"⏰ **{atr_s}**")
            col3.markdown(fase_s)

            # Alertas unificados (prazo + custo)
            if r["motivos"]:
                st.markdown("**Alertas:**")
                for m in r["motivos"]:
                    st.markdown(f"- 🔴 {m}")

            # Observações de marcos pendentes (com prev mas sem real)
            if not df_marcos_ve.empty and "observacao" in df_marcos_ve.columns:
                dm = df_marcos_ve[df_marcos_ve["projeto"] == r["projeto"]]
                obs_pend = dm[
                    dm["data_prevista"].notna() &
                    dm["data_realizada"].isna() &
                    dm["observacao"].str.strip().ne("")
                ]
                if not obs_pend.empty:
                    st.markdown("**Observações de Marcos Pendentes:**")
                    for _, mo in obs_pend.iterrows():
                        st.markdown(f"- **{mo['marco']}:** {mo['observacao']}")

            if st.button(
                "🔍 Ver detalhamento completo",
                key=f"ver_{r['projeto']}",
                use_container_width=True,
            ):
                st.session_state["ir_para_projeto"] = r["projeto"]
                st.session_state["ir_para_tab"] = "🔍 Detalhamento"
                st.switch_page(str(_ROOT / "pages" / "3_projetos.py"))

if not baixo.empty:
    with st.expander(f"🟢 {len(baixo)} projeto(s) em baixo risco"):
        for _, r in baixo.iterrows():
            pct_s = f"💰 {r['pct_projetado']:.0f}%" if pd.notna(r["pct_projetado"]) else "s/orçamento"
            st.markdown(f"🟢 **{r['nome_projeto']}** · {pct_s} · ✅ No prazo")

st.divider()

# ── 4. Exportar ───────────────────────────────────────────────────────────────
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
    "Ano":      st.session_state.get("filtro_anos", []),
    "Mês":      st.session_state.get("filtro_meses", []),
    "Status":   st.session_state.get("filtro_status", []),
}
try:
    pdf_bytes = gerar_relatorio_risco_pdf(risco, filtros_aplicados, df_f, df_custos_raw)
    col_pdf.download_button(
        "📄 Exportar PDF",
        pdf_bytes,
        "visao_executiva_riscos.pdf",
        "application/pdf",
        use_container_width=True,
    )
except Exception as e:
    col_pdf.caption(f"PDF indisponível: {e}")
