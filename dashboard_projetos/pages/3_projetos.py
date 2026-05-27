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

# ── CSS global ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* KPI cards */
div[data-testid="metric-container"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px 18px 10px;
}
div[data-testid="metric-container"] label { color: #64748b; font-size: 13px; }
div[data-testid="metric-container"] [data-testid="stMetricValue"] { font-size: 20px; font-weight: 700; }

/* Expander com borda sutil */
div[data-testid="stExpander"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
}

/* Barra de progresso mais espessa */
div[data-testid="stProgress"] > div > div { height: 10px !important; border-radius: 5px; }

/* Sidebar compacta */
section[data-testid="stSidebar"] { min-width: 240px !important; max-width: 260px !important; }
section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }

/* Timeline de marcos */
.marco-row { display:flex; align-items:center; gap:10px; padding:6px 0; border-bottom:1px solid #f0f4f8; }
.marco-nome { flex:2; font-size:13px; color:#334155; }
.marco-data { flex:1; font-size:13px; font-weight:600; color:#1e293b; text-align:center; }
.marco-badge { flex:1; text-align:center; font-size:12px; font-weight:600; border-radius:20px; padding:2px 10px; }
.badge-ok   { background:#dcfce7; color:#166534; }
.badge-atrasado { background:#fee2e2; color:#991b1b; }
.badge-previsto { background:#f1f5f9; color:#475569; }
.badge-vazio    { background:#f8fafc; color:#cbd5e1; }
</style>
""", unsafe_allow_html=True)

st.title("📈 Andamento dos Projetos")

df, df_custos_raw, df_horas_raw = agregar_tudo()

if df.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

# ── Opções ────────────────────────────────────────────────────────────────────
lista_projetos = sorted(df["nome_projeto"].dropna().unique().tolist())
lista_anos     = sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist()) if "ano" in df_custos_raw.columns else []
lista_meses    = sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist()) if "mes" in df_custos_raw.columns else []

if "filtro_projetos" not in st.session_state: st.session_state["filtro_projetos"] = lista_projetos
if "filtro_anos"     not in st.session_state: st.session_state["filtro_anos"]     = lista_anos
if "filtro_meses"    not in st.session_state: st.session_state["filtro_meses"]    = lista_meses

st.session_state["filtro_projetos"] = [p for p in st.session_state["filtro_projetos"] if p in lista_projetos]
st.session_state["filtro_anos"]     = [a for a in st.session_state["filtro_anos"]     if a in lista_anos]
st.session_state["filtro_meses"]    = [m for m in st.session_state["filtro_meses"]    if m in lista_meses]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filtros")
    projetos_selecionados = st.multiselect("Projetos:", options=lista_projetos,
        default=st.session_state["filtro_projetos"], key="filtro_projetos")
    anos_selecionados = st.multiselect("Ano:", options=lista_anos,
        default=st.session_state["filtro_anos"], key="filtro_anos")
    meses_selecionados = st.multiselect("Mês:", options=lista_meses,
        default=st.session_state["filtro_meses"], key="filtro_meses")
    if st.button("🔄 Limpar filtros", use_container_width=True):
        st.session_state["filtro_projetos"] = lista_projetos
        st.session_state["filtro_anos"]     = lista_anos
        st.session_state["filtro_meses"]    = lista_meses
        st.rerun()

# ── Filtros ───────────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────────
# VISÃO GERAL (tab 1) vs TIMELINE (tab 2) vs DETALHAMENTO (tab 3)
# ─────────────────────────────────────────────────────────────────────────────
tab_resumo, tab_timeline, tab_detalhe = st.tabs([
    "📊 Resumo Geral", "📅 Timeline de Projetos", "🔍 Detalhamento"
])

# ═══════════════════════════════════════════════════════════════════
# TAB 1 — RESUMO GERAL
# ═══════════════════════════════════════════════════════════════════
with tab_resumo:
    total_custo   = df_f["valor_total"].sum()
    total_horas   = df_f["horas_total"].sum()
    custo_h_medio = total_custo / total_horas if total_horas > 0 else 0
    total_orc     = df_f["orcamento"].sum() if tem_orc else 0
    saldo_total   = total_orc - total_custo if tem_orc else None
    n_proj        = len(df_f)
    n_atrasados   = 0

    hoje = datetime.today().date()
    for _, row in df_f.iterrows():
        prev = row.get("prev_lancamento")
        real = row.get("real_lancamento")
        if prev and str(prev) not in ("0","None","nan",""):
            try:
                dp = datetime.strptime(str(prev)[:10], "%Y-%m-%d").date()
                dr = datetime.strptime(str(real)[:10], "%Y-%m-%d").date() if real and str(real) not in ("0","None","nan","") else None
                ref = dr if dr else hoje
                if ref > dp:
                    n_atrasados += 1
            except Exception:
                pass

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("📁 Projetos ativos", str(n_proj))
    k2.metric("💰 Realizado",       formata_brl(total_custo))
    k3.metric("🎯 Orçamento",       formata_brl(total_orc) if tem_orc else "N/D")
    k4.metric("💹 Saldo",           formata_brl(saldo_total) if saldo_total is not None else "N/D",
              delta=f"{(total_custo/total_orc*100):.1f}% consumido" if tem_orc and total_orc > 0 else None,
              delta_color="inverse")
    k5.metric("⚠️ Com atraso",      str(n_atrasados))

    st.markdown("")

    # Gauges de orçamento
    if tem_orc:
        st.subheader("Consumo de Orçamento")
        n = len(df_f)
        gauge_cols = st.columns(min(n, 4))
        for i, (_, row) in enumerate(df_f.iterrows()):
            with gauge_cols[i % len(gauge_cols)]:
                st.plotly_chart(charts.gauge_orcamento(row["projeto"], row["pct_orcamento"]),
                                use_container_width=True)
        st.divider()
    else:
        st.plotly_chart(charts.grafico_realizado_por_projeto(df_f), use_container_width=True)
        st.divider()

    # Tabela de status rápido
    st.subheader("Status Rápido")

    def _fmt(val) -> str:
        if not val or str(val) in ("0","None","nan",""): return "—"
        try: return datetime.strptime(str(val)[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except: return str(val)

    def _status_lancamento(row) -> str:
        prev = row.get("prev_lancamento")
        real = row.get("real_lancamento")
        if not prev or str(prev) in ("0","None","nan",""): return "Sem data"
        try:
            dp  = datetime.strptime(str(prev)[:10], "%Y-%m-%d").date()
            dr  = datetime.strptime(str(real)[:10], "%Y-%m-%d").date() if real and str(real) not in ("0","None","nan","") else None
            ref = dr if dr else hoje
            diff = (ref - dp).days
            if dr:
                return f"✅ Lançado" if diff <= 0 else f"🔴 +{diff}d"
            else:
                return f"🟡 Em {diff}d" if diff > 0 else f"🔴 {abs(diff)}d atraso"
        except: return "—"

    rows_status = []
    for _, row in df_f.iterrows():
        pct = row.get("pct_orcamento", 0)
        rows_status.append({
            "🚦": cor_status(pct) if tem_orc and pct else "📋",
            "CC":           row["projeto"],
            "Projeto":      row["nome_projeto"],
            "Realizado":    formata_brl(row["valor_total"]),
            "Orçamento":    formata_brl(row["orcamento"]) if tem_orc and row.get("orcamento", 0) > 0 else "N/D",
            "% Orç.":       f"{pct:.0f}%" if tem_orc and pct else "—",
            "Horas":        f"{row['horas_total']:.0f} h",
            "Início CC":    _fmt(row.get("data_inicio")),
            "Lançamento Prev.": _fmt(row.get("prev_lancamento")),
            "Status Lançamento": _status_lancamento(row),
        })

    df_status = pd.DataFrame(rows_status)
    st.dataframe(df_status, use_container_width=True, hide_index=True)

    col_dl, _ = st.columns([1, 4])
    csv = df_status.to_csv(index=False).encode("utf-8")
    col_dl.download_button("⬇️ Exportar CSV", csv, "status_projetos.csv", "text/csv")

# ═══════════════════════════════════════════════════════════════════
# TAB 2 — TIMELINE DE PROJETOS
# ═══════════════════════════════════════════════════════════════════
with tab_timeline:
    st.subheader("📅 Visão Comparativa de Prazos")
    st.caption("Compara datas previstas vs realizadas de todos os marcos, por projeto.")

    MARCOS_DEF = [
        ("data_inicio",           None,                   "Início CC"),
        ("prev_viabilidade",      "real_viabilidade",     "Viabilidade"),
        ("prev_qualidade",        "real_qualidade",       "Qualidade"),
        ("prev_aprov_lancamento", "real_aprov_lancamento","Aprov. Lançamento"),
        ("prev_lancamento",       "real_lancamento",      "Lançamento"),
    ]

    def _parse(val):
        if not val or str(val) in ("0","None","nan",""): return None
        try: return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
        except: return None

    def _badge(prev_d, real_d, col_prev, col_real):
        if col_real is None:
            return "<span class='marco-badge badge-previsto'>—</span>"
        if not prev_d and not real_d:
            return "<span class='marco-badge badge-vazio'>Não informado</span>"
        if real_d:
            diff = (real_d - prev_d).days if prev_d else 0
            if diff <= 0:
                return f"<span class='marco-badge badge-ok'>✅ No prazo</span>"
            else:
                return f"<span class='marco-badge badge-atrasado'>🔴 +{diff}d</span>"
        else:
            if not prev_d: return "<span class='marco-badge badge-vazio'>Não informado</span>"
            diff = (hoje - prev_d).days
            if diff > 0:
                return f"<span class='marco-badge badge-atrasado'>⏳ {diff}d pendente</span>"
            else:
                return f"<span class='marco-badge badge-previsto'>🗓️ Em {abs(diff)}d</span>"

    for _, row in df_f.iterrows():
        with st.expander(f"**{row['projeto']}** — {row['nome_projeto']}", expanded=False):

            # Resumo financeiro compacto no topo
            fin1, fin2, fin3, fin4 = st.columns(4)
            fin1.metric("Realizado",    formata_brl(row["valor_total"]))
            fin2.metric("Orçamento",    formata_brl(row["orcamento"]) if row.get("orcamento",0) > 0 else "N/D")
            fin3.metric("Horas",        f"{row['horas_total']:.0f} h")
            fin4.metric("Custo/h",      formata_brl(row["custo_por_hora"]))

            if row.get("orcamento", 0) > 0:
                pct = row["pct_orcamento"]
                cor_prog = "#c0392b" if pct > 100 else ("#f39c12" if pct >= 80 else "#2ecc71")
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:10px;margin:6px 0 10px">
                    <div style="flex:1;background:#e2e8f0;border-radius:6px;height:10px;overflow:hidden">
                        <div style="width:{min(pct,100):.1f}%;background:{cor_prog};height:100%;border-radius:6px"></div>
                    </div>
                    <span style="font-size:13px;font-weight:600;color:{cor_prog}">{pct:.1f}% consumido</span>
                </div>""", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("**Cronograma de Marcos**")

            # Cabeçalho
            st.markdown("""
            <div class='marco-row' style='font-weight:700;font-size:12px;color:#94a3b8;border-bottom:2px solid #e2e8f0'>
                <div class='marco-nome'>Marco</div>
                <div class='marco-data'>Previsto</div>
                <div class='marco-data'>Realizado</div>
                <div class='marco-badge' style='flex:1;text-align:center'>Situação</div>
            </div>""", unsafe_allow_html=True)

            tem_qualquer_data = False
            for col_prev, col_real, nome in MARCOS_DEF:
                prev_v = row.get(col_prev)
                real_v = row.get(col_real) if col_real else None
                prev_d = _parse(prev_v)
                real_d = _parse(real_v)

                if not prev_d and not real_d:
                    continue
                tem_qualquer_data = True

                prev_str = prev_d.strftime("%d/%m/%Y") if prev_d else "—"
                real_str = real_d.strftime("%d/%m/%Y") if real_d else "—"
                badge    = _badge(prev_d, real_d, col_prev, col_real)

                st.markdown(f"""
                <div class='marco-row'>
                    <div class='marco-nome'>{nome}</div>
                    <div class='marco-data'>{prev_str}</div>
                    <div class='marco-data'>{real_str}</div>
                    {badge}
                </div>""", unsafe_allow_html=True)

            if not tem_qualquer_data:
                st.caption("ℹ️ Nenhuma data cadastrada. Acesse **Orçamentos** para informar.")

# ═══════════════════════════════════════════════════════════════════
# TAB 3 — DETALHAMENTO
# ═══════════════════════════════════════════════════════════════════
with tab_detalhe:
    st.subheader("🔍 Detalhamento por Projeto")

    proj_opcoes = df_f["nome_projeto"].tolist()
    proj_map    = dict(zip(df_f["nome_projeto"], df_f["projeto"]))

    projeto_detalhe = st.selectbox(
        "Selecione um projeto para detalhar:",
        options=proj_opcoes,
        format_func=lambda x: f"{proj_map.get(x,'')} — {x}"
    )

    row = df_f[df_f["nome_projeto"] == projeto_detalhe].iloc[0]
    cc  = row["projeto"]

    # Cabeçalho do projeto
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,#1e3a5f,#2563eb);border-radius:12px;
                padding:18px 24px;margin:10px 0 18px;color:white">
        <div style="font-size:20px;font-weight:700">{row['nome_projeto']}</div>
        <div style="font-size:13px;opacity:.8;margin-top:4px">
            CC: {cc}
            {"&nbsp;·&nbsp;" + str(row.get("filial","")) if row.get("filial","") not in ("","0") else ""}
            {"&nbsp;·&nbsp;" + str(row.get("area",""))   if row.get("area","")   not in ("","0") else ""}
            {"&nbsp;·&nbsp;" + str(row.get("segmento","")) if row.get("segmento","") not in ("","0") else ""}
        </div>
    </div>""", unsafe_allow_html=True)

    # KPIs do projeto
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("💰 Realizado",    formata_brl(row["valor_total"]))
    d2.metric("🎯 Orçamento",    formata_brl(row["orcamento"]) if row.get("orcamento",0) > 0 else "N/D")
    d3.metric("⏱️ Horas",        f"{row['horas_total']:.0f} h")
    d4.metric("👥 Colaboradores",str(int(row.get("n_colaboradores", 0))))

    if row.get("orcamento", 0) > 0:
        pct = row["pct_orcamento"]
        cor_prog = "#c0392b" if pct > 100 else ("#f39c12" if pct >= 80 else "#2ecc71")
        saldo_str = formata_brl(row["saldo_orcamento"])
        label_saldo = f"🚨 Estouro de {formata_brl(abs(row['saldo_orcamento']))}" if pct > 100 else f"✅ Saldo: {saldo_str}"
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:12px;margin:10px 0 16px">
            <div style="flex:1;background:#e2e8f0;border-radius:8px;height:14px;overflow:hidden">
                <div style="width:{min(pct,100):.1f}%;background:{cor_prog};height:100%;border-radius:8px"></div>
            </div>
            <span style="font-size:14px;font-weight:700;color:{cor_prog};white-space:nowrap">
                {pct:.1f}% — {label_saldo}
            </span>
        </div>""", unsafe_allow_html=True)

    st.divider()

    col_a, col_b = st.columns([1, 1])

    # Coluna A — Cronograma
    with col_a:
        st.markdown("#### 📅 Cronograma")
        MARCOS_DEF2 = [
            ("data_inicio",           None,                   "Início CC"),
            ("prev_viabilidade",      "real_viabilidade",     "Viabilidade"),
            ("prev_qualidade",        "real_qualidade",       "Qualidade"),
            ("prev_aprov_lancamento", "real_aprov_lancamento","Aprov. Lançamento"),
            ("prev_lancamento",       "real_lancamento",      "Lançamento"),
        ]

        def _parse(val):
            if not val or str(val) in ("0","None","nan",""): return None
            try: return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
            except: return None

        tem_data = False
        st.markdown("""
        <div class='marco-row' style='font-weight:700;font-size:12px;color:#94a3b8;border-bottom:2px solid #e2e8f0'>
            <div class='marco-nome'>Marco</div>
            <div class='marco-data'>Previsto</div>
            <div class='marco-data'>Realizado</div>
            <div class='marco-badge' style='flex:1;text-align:center'>Situação</div>
        </div>""", unsafe_allow_html=True)

        for col_prev, col_real, nome in MARCOS_DEF2:
            prev_d = _parse(row.get(col_prev))
            real_d = _parse(row.get(col_real)) if col_real else None
            if not prev_d and not real_d:
                continue
            tem_data = True
            prev_str = prev_d.strftime("%d/%m/%Y") if prev_d else "—"
            real_str = real_d.strftime("%d/%m/%Y") if real_d else "—"

            if col_real is None:
                badge = "<span class='marco-badge badge-previsto'>—</span>"
            elif real_d:
                diff = (real_d - prev_d).days if prev_d else 0
                badge = "<span class='marco-badge badge-ok'>✅ No prazo</span>" if diff <= 0 else f"<span class='marco-badge badge-atrasado'>🔴 +{diff}d</span>"
            else:
                if prev_d:
                    diff = (hoje - prev_d).days
                    badge = f"<span class='marco-badge badge-atrasado'>⏳ {diff}d pendente</span>" if diff > 0 else f"<span class='marco-badge badge-previsto'>🗓️ Em {abs(diff)}d</span>"
                else:
                    badge = "<span class='marco-badge badge-vazio'>Não informado</span>"

            st.markdown(f"""
            <div class='marco-row'>
                <div class='marco-nome'>{nome}</div>
                <div class='marco-data'>{prev_str}</div>
                <div class='marco-data'>{real_str}</div>
                {badge}
            </div>""", unsafe_allow_html=True)

        if not tem_data:
            st.caption("ℹ️ Sem datas cadastradas. Acesse **Orçamentos** para informar.")

    # Coluna B — Equipe
    with col_b:
        st.markdown("#### 👥 Equipe")
        colaboradores = str(row.get("colaboradores",""))
        if colaboradores and colaboradores not in ("0",""):
            lista_col = [c.strip() for c in colaboradores.split(",") if c.strip()]
            for col_name in lista_col:
                st.markdown(f"• {col_name}")
        else:
            st.caption("Sem dados de equipe.")

    # Gráfico de horas por colaborador
    if not df_horas_raw.empty and "c_custo" in df_horas_raw.columns:
        df_h_proj = df_horas_raw[df_horas_raw["c_custo"] == cc]
        if not df_h_proj.empty and "nome" in df_h_proj.columns:
            st.divider()
            st.markdown("#### ⏱️ Horas por Colaborador")
            st.plotly_chart(charts.grafico_horas_colaborador(df_h_proj, cc), use_container_width=True)

    # Custos mensais do projeto
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
                text=[f"R$ {v:,.0f}" for v in custo_mes["realizado"]],
                textposition="outside",
            ))
            fig_cm.update_layout(
                height=300,
                margin=dict(l=10,r=10,t=30,b=10),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                yaxis_tickprefix="R$ ", yaxis_tickformat=",.0f",
                showlegend=False,
            )
            st.plotly_chart(fig_cm, use_container_width=True)
