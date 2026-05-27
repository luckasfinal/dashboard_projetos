import sys
from pathlib import Path
from datetime import datetime, date
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from utils.db import init_db
from utils.data_processor import agregar_tudo, formata_brl, cor_status
from utils import charts

init_db()

# ── CSS — Badges Sólidas Obscuras/Claras de Alto Contraste ─────────────────────
st.markdown("""
<style>
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

div[data-testid="stExpander"] {
    border: 1px solid rgba(128,128,128,0.2) !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
}

.marco-header {
    display:flex; align-items:center; gap:8px;
    padding:5px 0; border-bottom:2px solid rgba(128,128,128,0.3);
    font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.05em; opacity:.6;
}
.marco-row {
    display:flex; align-items:center; gap:8px;
    padding:7px 0; border-bottom:1px solid rgba(128,128,128,0.12);
}
.marco-nome  { flex:2.2; font-size:13px; }
.marco-data  { flex:1.2; font-size:13px; font-weight:600; text-align:center; }
.marco-badge { flex:1.2; text-align:center; font-size:11px; font-weight:700; border-radius:12px; padding:4px 8px; white-space: nowrap; }

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

# ── Filtros Unificados Nativamente Sem Conflito de Estado ───────────────────
lista_projetos = sorted(df["nome_projeto"].dropna().unique().tolist())
lista_anos     = sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist()) if "ano" in df_custos_raw.columns else []
lista_meses    = sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist()) if "mes" in df_custos_raw.columns else []

if "sel_projetos" not in st.session_state: st.session_state["sel_projetos"] = lista_projetos
if "sel_anos"     not in st.session_state: st.session_state["sel_anos"]     = lista_anos
if "sel_meses"    not in st.session_state: st.session_state["sel_meses"]    = lista_meses

default_projetos = [p for p in st.session_state["sel_projetos"] if p in lista_projetos]
default_anos     = [a for a in st.session_state["sel_anos"] if a in lista_anos]
default_meses    = [m for m in st.session_state["sel_meses"] if m in lista_meses]

if not default_projetos: default_projetos = lista_projetos
if not default_anos: default_anos = lista_anos
if not default_meses: default_meses = lista_meses

with st.sidebar:
    st.header("🔍 Filtros")
    projetos_selecionados = st.multiselect("Projetos:", options=lista_projetos, default=default_projetos)
    anos_selecionados     = st.multiselect("Ano:", options=lista_anos, default=default_anos)
    meses_selecionados    = st.multiselect("Mês:", options=lista_meses, default=default_meses)
    
    if st.button("🔄 Limpar filtros", use_container_width=True):
        st.session_state["sel_projetos"] = lista_projetos
        st.session_state["sel_anos"]     = lista_anos
        st.session_state["sel_meses"]    = lista_meses
        st.rerun()

st.session_state["sel_projetos"] = projetos_selecionados
st.session_state["sel_anos"]     = anos_selecionados
st.session_state["sel_meses"]    = meses_selecionados

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
    st.info("💡 Nenhum projeto encontrado para os filtros selecionados.")
    st.stop()

tem_orc = (df_f.get("orcamento", pd.Series([0])) > 0).any()
hoje    = datetime.today().date()

# ── Parsers robustos contra múltiplos tipos de dados no DB ────────────────────
def _parse(val):
    if pd.isna(val) or not val or str(val).strip() in ("0","None","nan",""): 
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date()
    if isinstance(val, date):
        return val
    val_str = str(val).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try: return datetime.strptime(val_str, fmt).date()
        except ValueError: continue
    return None

def _fmt(val) -> str:
    d = _parse(val)
    return d.strftime("%d/%m/%Y") if d else "—"

def _badge(col_prev, col_real, prev_d, real_d) -> str:
    if not prev_d and not real_d:
        return "<span class='marco-badge badge-vazio'>—</span>"
    if real_d:
        diff = (real_d - prev_d).days if prev_d else 0
        return ("<span class='marco-badge badge-ok'>No prazo</span>" if diff <= 0 
                else f"<span class='marco-badge badge-atrasado'>+{diff}d</span>")
    if prev_d:
        diff = (hoje - prev_d).days
        return (f"<span class='marco-badge badge-atrasado'>{diff}d atraso</span>" if diff > 0 
                else f"<span class='marco-badge badge-futuro'>Em {abs(diff)}d</span>")
    return "<span class='marco-badge badge-vazio'>—</span>"

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
        <div class='marco-badge'>Situação</div>
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
# ABAS DO COMPONENTE principal
# ═══════════════════════════════════════════════════════════════════
tab_resumo, tab_timeline, tab_detalhe = st.tabs([
    "📊 Resumo Geral", "📅 Timeline de Projetos", "🔍 Detalhamento"
])

# ───────────────────────────────────────────────────────────────────
# ABA 1 — RESUMO GERAL (Correção do Chunking de Colunas Vazias)
# ───────────────────────────────────────────────────────────────────
with tab_resumo:
    total_custo   = df_f["valor_total"].sum()
    total_horas   = df_f["horas_total"].sum()
    total_orc     = df_f["orcamento"].sum() if tem_orc else 0
    saldo_total   = total_orc - total_custo if tem_orc else None
    pct_cons      = (total_custo / total_orc * 100) if tem_orc and total_orc > 0 else None
    
    n_atrasados = 0
    for _, row in df_f.iterrows():
        prev_d = _parse(row.get("prev_lancamento"))
        real_d = _parse(row.get("real_lancamento"))
        if prev_d and (real_d if real_d else hoje) > prev_d: 
            n_atrasados += 1

    r1c1, r1c2, r1c3 = st.columns(3)
    r1c1.metric("📁 Projetos ativos", str(len(df_f)))
    r1c2.metric("💰 Realizado",       formata_brl(total_custo))
    r1c3.metric("🎯 Orçamento",       formata_brl(total_orc) if tem_orc else "Não cadastrado")

    r2c1, r2c2, r2c3 = st.columns(3)
    r2c1.metric("💹 Saldo",         formata_brl(saldo_total) if saldo_total is not None else "N/D",
                delta=f"{pct_cons:.1f}% consumido" if pct_cons else None, delta_color="inverse")
    r2c2.metric("⏱️ Horas Totais",  f"{total_horas:,.0f} h")
    r2c3.metric("⚠️ Com atraso",    str(n_atrasados))

    st.markdown("")

    # Linha segura de gauges agrupada em lotes de até 4 colunas por linha
    df_orc_ativos = df_f[df_f["orcamento"] > 0] if "orcamento" in df_f.columns else pd.DataFrame()
    if not df_orc_ativos.empty:
        st.subheader("Consumo de Orçamento")
        for i in range(0, len(df_orc_ativos), 4):
            chunk = df_orc_ativos.iloc[i:i+4]
            cols = st.columns(len(chunk))
            for idx, (_, row) in enumerate(chunk.iterrows()):
                with cols[idx]:
                    nome_g = str(row.get("nome_projeto","")) or row["projeto"]
                    st.plotly_chart(charts.gauge_orcamento(nome_g, row["pct_orcamento"]), use_container_width=True, theme="streamlit")
        st.divider()

    st.subheader("Status Rápido")
    def _status_lanc(r) -> str:
        p_d = _parse(r.get("prev_lancamento"))
        r_d = _parse(r.get("real_lancamento"))
        if not p_d: return "Sem data"
        diff = ((r_d if r_d else hoje) - p_d).days
        if r_d: return "✅ Lançado" if diff <= 0 else f"🔴 +{diff}d"
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

# ───────────────────────────────────────────────────────────────────
# ABA 2 — TIMELINE DE PROJETOS
# ───────────────────────────────────────────────────────────────────
with tab_timeline:
    st.subheader("📅 Visão Comparativa de Prazos")
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

            marcos_html = _tabela_marcos_html(row)
            if marcos_html:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(marcos_html, unsafe_allow_html=True)
            else:
                st.caption("ℹ️ Nenhuma data de cronograma preenchida para este projeto.")

# ───────────────────────────────────────────────────────────────────
# ABA 3 — DETALHAMENTO (Proteção Absoluta Contra IndexError)
# ───────────────────────────────────────────────────────────────────
with tab_detalhe:
    st.subheader("🔍 Detalhes Individuais por Projeto")

    proj_opcoes = df_f["nome_projeto"].dropna().unique().tolist()
    proj_map    = dict(zip(df_f["nome_projeto"], df_f["projeto"]))

    if not proj_opcoes:
        st.info("Nenhum projeto disponível com a combinação atual de filtros.")
    else:
        # Prevenção de quebra de estado: força re-seleção se o item em memória sumir
        if "txt_projeto_detalhe" not in st.session_state or st.session_state["txt_projeto_detalhe"] not in proj_opcoes:
            st.session_state["txt_projeto_detalhe"] = proj_opcoes[0]

        projeto_detalhe = st.selectbox(
            "Selecione um projeto:",
            options=proj_opcoes,
            index=proj_opcoes.index(st.session_state["txt_projeto_detalhe"]),
            format_func=lambda x: f"{proj_map.get(x,'')} — {x}"
        )
        st.session_state["txt_projeto_detalhe"] = projeto_detalhe

        # Validação segura do dataframe filtrado
        df_alvo = df_f[df_f["nome_projeto"] == projeto_detalhe]
        if df_alvo.empty:
            st.warning("⚠️ O projeto selecionado não pôde ser carregado no contexto atual.")
        else:
            row = df_alvo.iloc[0]
            cc  = row["projeto"]

            extras = " · ".join(str(row.get(c,"")) for c in ["filial","area","segmento"] if row.get(c,"") not in ("","0",0))
            st.markdown(f"""
            <div style="background:linear-gradient(90deg,rgba(37,99,235,.15),rgba(37,99,235,.02));
                        border:1px solid rgba(37,99,235,.25);border-radius:12px;padding:16px 22px;margin:10px 0 18px">
                <div style="font-size:18px;font-weight:700">{row['nome_projeto']}</div>
                <div style="font-size:12px;opacity:.7;margin-top:4px">CC: {cc}{(' · ' + extras) if extras else ''}</div>
            </div>""", unsafe_allow_html=True)

            d1, d2, d3, d4 = st.columns(4)
            d1.metric("💰 Realizado",    formata_brl(row["valor_total"]))
            d2.metric("🎯 Orçamento",    formata_brl(row["orcamento"]) if row.get("orcamento",0) > 0 else "N/D")
            d3.metric("⏱️ Horas",        f"{row['horas_total']:.0f} h")
            d4.metric("📐 Custo/h",      formata_brl(row["custo_por_hora"]))

            if row.get("orcamento",0) > 0:
                pct = row["pct_orcamento"]
                cor = "#dc2626" if pct > 100 else ("#f59e0b" if pct >= 80 else "#22c55e")
                st.markdown(f"""
                <div style="display:flex;align-items:center;gap:12px;margin:10px 0 16px">
                    <div style="flex:1;background:rgba(128,128,128,.2);border-radius:8px;height:10px;overflow:hidden">
                        <div style="width:{min(pct,100):.1f}%;background:{cor};height:100%"></div>
                    </div>
                    <span style="font-size:13px;font-weight:700;color:{cor}">{pct:.1f}% consumido</span>
                </div>""", unsafe_allow_html=True)

            st.divider()
            col_cron, col_eq = st.columns([3, 2])

            with col_cron:
                st.markdown("#### 📅 Marcos Cronograma")
                m_html = _tabela_marcos_html(row)
                st.markdown(m_html if m_html else "<span style='opacity:.5'>Sem dados.</span>", unsafe_allow_html=True)

            with col_eq:
                st.markdown("#### 👥 Equipe Alocada")
                colaboradores = str(row.get("colaboradores",""))
                if colaboradores and colaboradores not in ("0","nan",""):
                    for c in [c.strip() for c in colaboradores.split(",") if c.strip()]:
                        st.markdown(f"• {c}")
                else:
                    st.caption("Sem dados de equipe.")

            # Seção de gráficos internos com verificação de dados vazios e tema explícito
            if not df_horas_raw.empty and "c_custo" in df_horas_raw.columns:
                df_h_proj = df_horas_raw[df_horas_raw["c_custo"] == cc]
                if not df_h_proj.empty and "nome" in df_h_proj.columns:
                    st.divider()
                    st.markdown("#### ⏱️ Distribuição de Horas por Colaborador")
                    st.plotly_chart(charts.grafico_horas_colaborador(df_h_proj, row.get("nome_projeto", cc)), use_container_width=True, theme="streamlit")

            if not df_custos_raw.empty and "centro_de_custo" in df_custos_raw.columns:
                df_c_proj = df_custos_raw[df_custos_raw["centro_de_custo"] == cc]
                if not df_c_proj.empty and "mes_ref" in df_c_proj.columns:
                    custo_mes = df_c_proj.groupby("mes_ref")["realizado"].sum().reset_index().sort_values("mes_ref")
                    if not custo_mes.empty:
                        st.divider()
                        st.markdown("#### 📈 Evolução Mensal de Desembolsos")
                        import plotly.graph_objects as go
                        fig_cm = go.Figure(go.Bar(
                            x=custo_mes["mes_ref"], y=custo_mes["realizado"],
                            marker_color="#2563eb",
                            text=[f"R$ {v:,.0f}" for v in custo_mes["realizado"]],
                            textposition="auto",
                            hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>",
                        ))
                        fig_cm.update_layout(
                            height=280, margin=dict(l=10,r=10,t=20,b=10),
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            xaxis=dict(gridcolor="rgba(128,128,128,0.1)"),
                            yaxis=dict(tickprefix="R$ ", gridcolor="rgba(128,128,128,.15)"),
                            showlegend=False,
                        )
                        st.plotly_chart(fig_cm, use_container_width=True, theme="streamlit")
