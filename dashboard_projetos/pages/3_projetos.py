import sys
from pathlib import Path
from datetime import datetime
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from utils.db import init_db
from utils.data_processor import agregar_tudo, formata_brl, cor_status
from utils import charts

init_db()

# ── CSS — tema neutro com Badges Sólidas de Alta Legibilidade ─────────────────
st.markdown("""
<style>
/* KPI cards */
div[data-testid="metric-container"] {
    border: 1px solid rgba(128,128,128,0.25);
    border-radius: 10px;
    padding: 12px 14px 8px;
    min-width: 0;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: clamp(14px, 2vw, 20px) !important;
    font-weight: 700;
    white-space: nowrap;
    overflow: visible !important;
    text-overflow: unset !important;
}
div[data-testid="metric-container"] label { font-size: 12px; opacity: 0.7; }

/* Expander */
div[data-testid="stExpander"] {
    border: 1px solid rgba(128,128,128,0.2) !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
}
/* Barra de progresso mais espessa */
div[data-testid="stProgress"] > div > div { height: 10px !important; border-radius: 5px; }

/* Sidebar */
section[data-testid="stSidebar"] { min-width: 240px !important; max-width: 260px !important; }
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }

/* Tabela de marcos estruturada */
.marco-header {
    display:flex; align-items:center; gap:8px;
    padding:5px 0; border-bottom:2px solid rgba(128,128,128,0.3);
    font-size:11px; font-weight:700; text-transform:uppercase;
    letter-spacing:.05em; opacity:.6;
}
.marco-row {
    display:flex; align-items:center; gap:8px;
    padding:7px 0; border-bottom:1px solid rgba(128,128,128,0.12);
}
.marco-nome  { flex:2.2; font-size:13px; }
.marco-data  { flex:1.2; font-size:13px; font-weight:600; text-align:center; }
.marco-badge { flex:1.2; text-align:center; font-size:11px; font-weight:700;
               border-radius:12px; padding:4px 8px; white-space: nowrap; }

/* Cores das Badges ajustadas para contraste perfeito (Fundo Sólido) */
.badge-ok        { background:#16a34a; color:white; }
.badge-atrasado  { background:#dc2626; color:white; }
.badge-pendente  { background:#ca8a04; color:white; }
.badge-futuro    { background:#2563eb; color:white; }
.badge-vazio     { background:#6b7280; color:white; }
</style>
""", unsafe_allow_html=True)

st.title("📈 Andamento dos Projetos")

df, df_custos_raw, df_horas_raw = agregar_tudo()

if df.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

lista_projetos = sorted(df["nome_projeto"].dropna().unique().tolist())
lista_anos     = sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist()) if "ano" in df_custos_raw.columns else []
lista_meses    = sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist()) if "mes" in df_custos_raw.columns else []

if "filtro_projetos" not in st.session_state: st.session_state["filtro_projetos"] = lista_projetos
if "filtro_anos"     not in st.session_state: st.session_state["filtro_anos"]     = lista_anos
if "filtro_meses"    not in st.session_state: st.session_state["filtro_meses"]    = lista_meses

st.session_state["filtro_projetos"] = [p for p in st.session_state["filtro_projetos"] if p in lista_projetos]
st.session_state["filtro_anos"]     = [a for a in st.session_state["filtro_anos"]     if a in lista_anos]
st.session_state["filtro_meses"]    = [m for m in st.session_state["filtro_meses"]    if m in lista_meses]

# ── Sidebar — Removido o argumento 'default' conflitante ──────────────────────
with st.sidebar:
    st.header("🔍 Filtros")
    projetos_selecionados = st.multiselect("Projetos:", options=lista_projetos, key="filtro_projetos")
    anos_selecionados = st.multiselect("Ano:", options=lista_anos, key="filtro_anos")
    meses_selecionados = st.multiselect("Mês:", options=lista_meses, key="filtro_meses")
    
    if st.button("🔄 Limpar filtros", use_container_width=True):
        st.session_state["filtro_projetos"] = lista_projetos
        st.session_state["filtro_anos"]     = lista_anos
        st.session_state["filtro_meses"]    = lista_meses
        st.rerun()

df_f = df.copy()
if projetos_selecionados:
    df_f = df_f[df_f["nome_projeto"].isin(projetos_selecionados)]
if anos_selecionados and "ano" in df_custos_raw.columns:
    cc = df_custos_raw[df_custos_raw["ano"].astype(str).isin(anos_selecionados)]["centro_de_custo"].unique()
    df_f = df_f[df_f["projeto"].isin(cc)]
if meses_selecionados and "mes" in df_custos_raw.columns:
    cc = df_custos_raw[df_custos_raw["mes"].astype(str).isin(meses_selecionados)]["centro_de_custo"].unique()
    df_f = df_f[df_f["projeto"].isin(cc)]

if df_f.empty:
    st.info("Nenhum projeto encontrado para os filtros selecionados.")
    st.stop()

tem_orc = (df_f.get("orcamento", pd.Series([0])) > 0).any()
hoje    = datetime.today().date()

# ── helpers ───────────────────────────────────────────────────────────────────
def _parse(val):
    if not val or str(val) in ("0","None","nan",""): return None
    try: return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except: return None

def _fmt(val) -> str:
    d = _parse(val)
    return d.strftime("%d/%m/%Y") if d else "—"

def _badge(col_prev, col_real, prev_d, real_d) -> str:
    if col_real is None:
        return "<span class='marco-badge badge-vazio'>—</span>"
    if not prev_d and not real_d:
        return "<span class='marco-badge badge-vazio'>Não informado</span>"
    if real_d:
        diff = (real_d - prev_d).days if prev_d else 0
        return ("<span class='marco-badge badge-ok'>No prazo</span>"
                if diff <= 0
                else f"<span class='marco-badge badge-atrasado'>+{diff}d</span>")
    if prev_d:
        diff = (hoje - prev_d).days
        return (f"<span class='marco-badge badge-atrasado'>{diff}d atraso</span>"
                if diff > 0
                else f"<span class='marco-badge badge-futuro'>Em {abs(diff)}d</span>")
    return "<span class='marco-badge badge-vazio'>Não informado</span>"

MARCOS_DEF = [
    ("data_inicio",           None,                   "Início CC"),
    ("prev_viabilidade",      "real_viabilidade",     "Viabilidade"),
    ("prev_qualidade",        "real_qualidade",       "Qualidade"),
    ("prev_aprov_lancamento", "real_aprov_lancamento","Aprov. Lançamento"),
    ("prev_lancamento",       "real_lancamento",      "Lançamento"),
]

def _tabela_marcos_html(row) -> str:
    html = """
    <div class='marco-header'>
        <div class='marco-nome'>Marco</div>
        <div class='marco-data'>Previsto</div>
        <div class='marco-data'>Realizado</div>
        <div class='marco-badge' style='flex:1.2;text-align:center'>Situação</div>
    </div>"""
    tem = False
    for col_prev, col_real, nome in MARCOS_DEF:
        prev_d = _parse(row.get(col_prev))
        real_d = _parse(row.get(col_real)) if col_real else None
        if not prev_d and not real_d: continue
        tem = True
        html += f"""
        <div class='marco-row'>
            <div class='marco-nome'>{nome}</div>
            <div class='marco-data'>{prev_d.strftime('%d/%m/%Y') if prev_d else '—'}</div>
            <div class='marco-data'>{real_d.strftime('%d/%m/%Y') if real_d else '—'}</div>
            {_badge(col_prev, col_real, prev_d, real_d)}
        </div>"""
    return html if tem else ""

# ═══════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════
tab_resumo, tab_timeline, tab_detalhe = st.tabs([
    "📊 Resumo Geral", "📅 Timeline de Projetos", "🔍 Detalhamento"
])

# ───────────────────────────────────────────────────────────────────
# TAB 1 — RESUMO GERAL
# ───────────────────────────────────────────────────────────────────
with tab_resumo:
    total_custo   = df_f["valor_total"].sum()
    total_horas   = df_f["horas_total"].sum()
    custo_h_medio = total_custo / total_horas if total_horas > 0 else 0
    total_orc     = df_f["orcamento"].sum() if tem_orc else 0
    saldo_total   = total_orc - total_custo if tem_orc else None
    pct_cons      = (total_custo / total_orc * 100) if tem_orc and total_orc > 0 else None
    n_proj        = len(df_f)

    n_atrasados = 0
    for _, row in df_f.iterrows():
        prev_d = _parse(row.get("prev_lancamento"))
        real_d = _parse(row.get("real_lancamento"))
        if prev_d:
            ref = real_d if real_d else hoje
            if ref > prev_d: n_atrasados += 1

    r1c1, r1c2, r1c3 = st.columns(3)
    r1c1.metric("📁 Projetos ativos", str(n_proj))
    r1c2.metric("💰 Realizado",       formata_brl(total_custo))
    r1c3.metric("🎯 Orçamento",       formata_brl(total_orc) if tem_orc else "Não cadastrado")

    r2c1, r2c2, r2c3 = st.columns(3)
    r2c1.metric("💹 Saldo",         formata_brl(saldo_total) if saldo_total is not None else "N/D",
                delta=f"{pct_cons:.1f}% consumido" if pct_cons else None, delta_color="inverse")
    r2c2.metric("⏱️ Horas Totais",  f"{total_horas:,.0f} h")
    r2c3.metric("⚠️ Com atraso",    str(n_atrasados))

    st.markdown("")

    if tem_orc:
        st.subheader("Consumo de Orçamento")
        n = len(df_f)
        gauge_cols = st.columns(min(n, 4))
        for i, (_, row) in enumerate(df_f.iterrows()):
            with gauge_cols[i % len(gauge_cols)]:
                nome_gauge = str(row.get("nome_projeto","")) or row["projeto"]
                st.plotly_chart(
                    charts.gauge_orcamento(nome_gauge, row["pct_orcamento"]),
                    use_container_width=True, theme="streamlit"
                )
        st.divider()
    else:
        st.plotly_chart(charts.grafico_realizado_por_projeto(df_f), use_container_width=True, theme="streamlit")
        st.divider()

    st.subheader("Status Rápido")

    def _status_lanc(row) -> str:
        prev_d = _parse(row.get("prev_lancamento"))
        real_d = _parse(row.get("real_lancamento"))
        if not prev_d: return "Sem data"
        ref  = real_d if real_d else hoje
        diff = (ref - prev_d).days
        if real_d:
            return "✅ Lançado" if diff <= 0 else f"🔴 +{diff}d"
        return f"🟡 Em {abs(diff)}d" if diff < 0 else f"🔴 {diff}d atraso"

    rows_st = []
    for _, row in df_f.iterrows():
        pct = row.get("pct_orcamento", 0)
        rows_st.append({
            "🚦":                  cor_status(pct) if tem_orc and pct else "📋",
            "Projeto":             row.get("nome_projeto", row["projeto"]),
            "CC":                  row["projeto"],
            "Realizado":           formata_brl(row["valor_total"]),
            "Orçamento":           formata_brl(row["orcamento"]) if tem_orc and row.get("orcamento",0) > 0 else "N/D",
            "% Orç.":              f"{pct:.0f}%" if tem_orc and pct else "—",
            "Horas":               f"{row['horas_total']:.0f} h",
            "Início CC":           _fmt(row.get("data_inicio")),
            "Lançamento Prev.":    _fmt(row.get("prev_lancamento")),
            "Status Lançamento":   _status_lanc(row),
        })

    st.dataframe(pd.DataFrame(rows_st), use_container_width=True, hide_index=True)
    col_dl, _ = st.columns([1,4])
    col_dl.download_button("⬇️ Exportar CSV",
        pd.DataFrame(rows_st).to_csv(index=False).encode("utf-8"),
        "status_projetos.csv","text/csv")

# ───────────────────────────────────────────────────────────────────
# TAB 2 — TIMELINE
# ───────────────────────────────────────────────────────────────────
with tab_timeline:
    st.subheader("📅 Visão Comparativa de Prazos")
    st.caption("Datas previstas vs realizadas de todos os marcos, por projeto.")

    for _, row in df_f.iterrows():
        nome_proj = row.get("nome_projeto","") or row["projeto"]
        cc        = row["projeto"]
        pct       = row.get("pct_orcamento", 0)
        semaforo  = cor_status(pct) if tem_orc and pct else "📋"

        with st.expander(f"{semaforo} **{nome_proj}** `{cc}`", expanded=False):
            fin1, fin2, fin3, fin4 = st.columns(4)
            fin1.metric("Realizado",  formata_brl(row["valor_total"]))
            fin2.metric("Orçamento",  formata_brl(row["orcamento"]) if row.get("orcamento",0) > 0 else "N/D")
            fin3.metric("Horas",      f"{row['horas_total']:.0f} h")
            fin4.metric("Custo/h",    formata_brl(row["custo_por_hora"]))

            if row.get("orcamento",0) > 0:
                p = row["pct_orcamento"]
                cor = "#dc2626" if p > 100 else ("#f59e0b" if p >= 80 else "#22c55e")
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:10px;margin:8px 0">
                    <div style="flex:1;background:rgba(128,128,128,.2);border-radius:6px;height:8px;overflow:hidden">
                        <div style="width:{min(p,100):.1f}%;background:{cor};height:100%;border-radius:6px"></div>
                    </div>
                    <span style="font-size:13px;font-weight:700;color:{cor};white-space:nowrap">{p:.1f}% consumido</span>
                </div>""", unsafe_allow_html=True)

            marcos_html = _tabela_marcos_html(row)
            if marcos_html:
                st.markdown("---")
                st.markdown(marcos_html, unsafe_allow_html=True)
            else:
                st.caption("ℹ️ Sem datas cadastradas. Acesse **Orçamentos** para informar.")

# ───────────────────────────────────────────────────────────────────
# TAB 3 — DETALHAMENTO
# ───────────────────────────────────────────────────────────────────
with tab_detalhe:
    st.subheader("🔍 Detalhamento por Projeto")

    # Filtro sem nomes duplicados
    proj_opcoes = df_f["nome_projeto"].dropna().unique().tolist()
    proj_map    = dict(zip(df_f["nome_projeto"], df_f["projeto"]))

    projeto_detalhe = st.selectbox(
        "Selecione um projeto:",
        options=proj_opcoes,
        format_func=lambda x: f"{proj_map.get(x,'')} — {x}"
    )

    row = df_f[df_f["nome_projeto"] == projeto_detalhe].iloc[0]
    cc  = row["projeto"]

    extras = " · ".join(
        str(row.get(c,"")) for c in ["filial","area","segmento"]
        if row.get(c,"") not in ("","0",0)
    )
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,rgba(37,99,235,.2),rgba(37,99,235,.05));
                border:1px solid rgba(37,99,235,.3);border-radius:12px;
                padding:16px 22px;margin:10px 0 18px">
        <div style="font-size:19px;font-weight:700">{row['nome_projeto']}</div>
        <div style="font-size:12px;opacity:.7;margin-top:4px">
            CC: {cc}{(' · ' + extras) if extras else ''}
        </div>
    </div>""", unsafe_allow_html=True)

    d1, d2, d3 = st.columns(3)
    d1.metric("💰 Realizado",    formata_brl(row["valor_total"]))
    d2.metric("🎯 Orçamento",    formata_brl(row["orcamento"]) if row.get("orcamento",0) > 0 else "N/D")
    d3.metric("⏱️ Horas",        f"{row['horas_total']:.0f} h")

    d4, d5, d6 = st.columns(3)
    d4.metric("📐 Custo/h",      formata_brl(row["custo_por_hora"]))
    d5.metric("👥 Colaboradores",str(int(row.get("n_colaboradores", 0))))
    saldo_proj = row.get("saldo_orcamento", 0)
    d6.metric("💹 Saldo",        formata_brl(saldo_proj) if row.get("orcamento",0) > 0 else "N/D")

    if row.get("orcamento",0) > 0:
        pct = row["pct_orcamento"]
        cor = "#dc2626" if pct > 100 else ("#f59e0b" if pct >= 80 else "#22c55e")
        label_extra = (f" — 🚨 Estouro de {formata_brl(abs(saldo_proj))}"
                       if pct > 100
                       else f" — Saldo: {formata_brl(saldo_proj)}")
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;margin:10px 0 16px">
            <div style="flex:1;background:rgba(128,128,128,.2);border-radius:8px;height:12px;overflow:hidden">
                <div style="width:{min(pct,100):.1f}%;background:{cor};height:100%;border-radius:8px"></div>
            </div>
            <span style="font-size:14px;font-weight:700;color:{cor};white-space:nowrap">
                {pct:.1f}%{label_extra}
            </span>
        </div>""", unsafe_allow_html=True)

    st.divider()

    col_cron, col_eq = st.columns([3, 2])

    with col_cron:
        st.markdown("#### 📅 Cronograma")
        marcos_html = _tabela_marcos_html(row)
        if marcos_html:
            st.markdown(marcos_html, unsafe_allow_html=True)
        else:
            st.caption("ℹ️ Sem datas.")

    with col_eq:
        st.markdown("#### 👥 Equipe")
        colaboradores = str(row.get("colaboradores",""))
        if colaboradores and colaboradores not in ("0",""):
            for c in [c.strip() for c in colaboradores.split(",") if c.strip()]:
                st.markdown(f"• {c}")
        else:
            st.caption("Sem dados de equipe.")

    if not df_horas_raw.empty and "c_custo" in df_horas_raw.columns:
        df_h_proj = df_horas_raw[df_horas_raw["c_custo"] == cc]
        if not df_h_proj.empty and "nome" in df_h_proj.columns:
            st.divider()
            st.markdown("#### ⏱️ Horas por Colaborador")
            st.plotly_chart(charts.grafico_horas_colaborador(df_h_proj, row.get("nome_projeto", cc)),
                            use_container_width=True, theme="streamlit")

    if not df_custos_raw.empty and "centro_de_custo" in df_custos_raw.columns:
        df_c_proj = df_custos_raw[df_custos_raw["centro_de_custo"] == cc]
        if not df_c_proj.empty and "mes_ref" in df_c_proj.columns:
            st.divider()
            st.markdown("#### 📈 Evolução Mensal de Custos")
            custo_mes = (df_c_proj.groupby("mes_ref")["realizado"].sum()
                         .reset_index().sort_values("mes_ref"))
            
            import plotly.graph_objects as go
            fig_cm = go.Figure(go.Bar(
                x=custo_mes["mes_ref"], y=custo_mes["realizado"],
                marker_color="#2563eb",
                marker_line_width=0,
                text=[f"R$ {v:,.0f}" for v in custo_mes["realizado"]],
                textposition="auto", # Posicionamento automático que respeita fontes e temas
                hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>",
            ))
            fig_cm.update_layout(
                height=300,
                margin=dict(l=10,r=10,t=30,b=10),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(gridcolor="rgba(128,128,128,0.1)"),
                yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(128,128,128,.15)"),
                showlegend=False,
            )
            st.plotly_chart(fig_cm, use_container_width=True, theme="streamlit") # Força integração perfeita com o tema ativo
