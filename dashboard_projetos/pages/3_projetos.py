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

st.markdown("""
<style>
div[data-testid="metric-container"] {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 10px;
    padding: 12px 14px 8px;
    min-width: 0;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: clamp(13px, 1.8vw, 19px) !important;
    font-weight: 700;
    white-space: nowrap;
    overflow: visible !important;
}
div[data-testid="metric-container"] label { font-size: 12px; opacity: .7; }
div[data-testid="stExpander"] {
    border: 1px solid rgba(128,128,128,.2) !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
}
section[data-testid="stSidebar"] { min-width: 240px !important; max-width: 260px !important; }

/* Tabela de marcos */
.marco-header {
    display:flex; gap:8px; padding:5px 0;
    border-bottom:2px solid rgba(128,128,128,.3);
    font-size:11px; font-weight:700; text-transform:uppercase;
    letter-spacing:.05em; opacity:.6;
}
.marco-row {
    display:flex; gap:8px; padding:7px 0;
    border-bottom:1px solid rgba(128,128,128,.12);
}
.marco-nome  { flex:2.2; font-size:13px; }
.marco-data  { flex:1.2; font-size:13px; font-weight:600; text-align:center; }
.marco-badge { flex:1.2; text-align:center; font-size:12px; font-weight:700;
               border-radius:20px; padding:3px 10px; }
.badge-ok        { background:rgba(22,163,74,.25);  color:#4ade80; }
.badge-atrasado  { background:rgba(220,38,38,.25);  color:#f87171; }
.badge-pendente  { background:rgba(234,179,8,.2);   color:#fbbf24; }
.badge-futuro    { background:rgba(99,102,241,.2);  color:#a5b4fc; }
.badge-vazio     { background:rgba(128,128,128,.12);color:rgba(128,128,128,.5); }
</style>
""", unsafe_allow_html=True)

st.title("📈 Andamento dos Projetos")

df, df_custos_raw, df_horas_raw = agregar_tudo()

if df.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

# ── Filtros persistentes ──────────────────────────────────────────────────────
lista_projetos = sorted(df["nome_projeto"].dropna().unique().tolist())
lista_anos     = sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist()) if "ano" in df_custos_raw.columns else []
lista_meses    = sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist()) if "mes" in df_custos_raw.columns else []

if "filtro_projetos" not in st.session_state: st.session_state["filtro_projetos"] = lista_projetos
if "filtro_anos"     not in st.session_state: st.session_state["filtro_anos"]     = lista_anos
if "filtro_meses"    not in st.session_state: st.session_state["filtro_meses"]    = lista_meses

st.session_state["filtro_projetos"] = [p for p in st.session_state["filtro_projetos"] if p in lista_projetos]
st.session_state["filtro_anos"]     = [a for a in st.session_state["filtro_anos"]     if a in lista_anos]
st.session_state["filtro_meses"]    = [m for m in st.session_state["filtro_meses"]    if m in lista_meses]

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

# ── Aplicação dos filtros ─────────────────────────────────────────────────────
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

# ── Helpers ───────────────────────────────────────────────────────────────────
def _parse(val):
    if not val or str(val) in ("0", "None", "nan", ""): return None
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
        return ("<span class='marco-badge badge-ok'>✅ No prazo</span>"
                if diff <= 0
                else f"<span class='marco-badge badge-atrasado'>🔴 +{diff}d</span>")
    if prev_d:
        diff = (hoje - prev_d).days
        return (f"<span class='marco-badge badge-pendente'>⏳ {diff}d pendente</span>"
                if diff > 0
                else f"<span class='marco-badge badge-futuro'>🗓️ Em {abs(diff)}d</span>")
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
        if not prev_d and not real_d:
            continue
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
# TABS — removida a aba "Timeline de Projetos"
# ═══════════════════════════════════════════════════════════════════
tab_resumo, tab_detalhe = st.tabs(["📊 Resumo Geral", "🔍 Detalhamento"])

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
            if ref > prev_d:
                n_atrasados += 1

    r1c1, r1c2, r1c3 = st.columns(3)
    r1c1.metric("📁 Projetos ativos", str(n_proj))
    r1c2.metric("💰 Realizado",       formata_brl(total_custo))
    r1c3.metric("🎯 Orçamento",       formata_brl(total_orc) if tem_orc else "Não cadastrado")

    r2c1, r2c2, r2c3 = st.columns(3)
    r2c1.metric("💹 Saldo",        formata_brl(saldo_total) if saldo_total is not None else "N/D",
                delta=f"{pct_cons:.1f}% consumido" if pct_cons else None, delta_color="inverse")
    r2c2.metric("⏱️ Horas Totais", f"{total_horas:,.0f} h")
    r2c3.metric("⚠️ Com atraso",   str(n_atrasados))

    st.markdown("")

    if tem_orc:
        st.subheader("Consumo de Orçamento")
        n = len(df_f)
        gauge_cols = st.columns(min(n, 4))
        for i, (_, row) in enumerate(df_f.iterrows()):
            with gauge_cols[i % len(gauge_cols)]:
                nome_gauge = str(row.get("nome_projeto", "")) or row["projeto"]
                st.plotly_chart(
                    charts.gauge_orcamento(nome_gauge, row["pct_orcamento"]),
                    use_container_width=True,
                )
        st.divider()
    else:
        st.plotly_chart(charts.grafico_realizado_por_projeto(df_f), use_container_width=True)
        st.divider()

    # Tabela de status
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
            "🚦":               cor_status(pct) if tem_orc and pct else "📋",
            "Projeto":          row.get("nome_projeto", row["projeto"]),
            "CC":               row["projeto"],
            "Realizado":        formata_brl(row["valor_total"]),
            "Orçamento":        formata_brl(row["orcamento"]) if tem_orc and row.get("orcamento", 0) > 0 else "N/D",
            "% Orç.":           f"{pct:.0f}%" if tem_orc and pct else "—",
            "Horas":            f"{row['horas_total']:.0f} h",
            "Início CC":        _fmt(row.get("data_inicio")),
            "Lançamento Prev.": _fmt(row.get("prev_lancamento")),
            "Status":           _status_lanc(row),
        })

    st.dataframe(pd.DataFrame(rows_st), use_container_width=True, hide_index=True)
    col_dl, _ = st.columns([1, 4])
    col_dl.download_button("⬇️ Exportar CSV",
        pd.DataFrame(rows_st).to_csv(index=False).encode("utf-8"),
        "status_projetos.csv", "text/csv")

# ───────────────────────────────────────────────────────────────────
# TAB 2 — DETALHAMENTO
# ───────────────────────────────────────────────────────────────────
with tab_detalhe:
    st.subheader("🔍 Detalhamento por Projeto")

    proj_opcoes = df_f["nome_projeto"].tolist()
    proj_map    = dict(zip(df_f["nome_projeto"], df_f["projeto"]))

    projeto_detalhe = st.selectbox(
        "Selecione um projeto:",
        options=proj_opcoes,
        format_func=lambda x: f"{proj_map.get(x, '')} — {x}",
    )

    row = df_f[df_f["nome_projeto"] == projeto_detalhe].iloc[0]
    cc  = row["projeto"]

    # Header do projeto
    extras = " · ".join(
        str(row.get(c, "")) for c in ["filial", "area", "segmento"]
        if row.get(c, "") not in ("", "0", 0)
    )
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,rgba(37,99,235,.6),rgba(37,99,235,.25));
                border:1px solid rgba(37,99,235,.4);border-radius:12px;
                padding:16px 22px;margin:10px 0 18px">
        <div style="font-size:19px;font-weight:700">{row['nome_projeto']}</div>
        <div style="font-size:12px;opacity:.7;margin-top:4px">
            CC: {cc}{(' · ' + extras) if extras else ''}
        </div>
    </div>""", unsafe_allow_html=True)

    # ── KPIs do projeto — 5 indicadores em 2 linhas ──────────────────────────
    saldo_proj = row.get("saldo_orcamento", 0) if row.get("orcamento", 0) > 0 else None

    # Linha 1: Realizado | Orçamento | Saldo
    kp1, kp2, kp3 = st.columns(3)
    kp1.metric("💰 Realizado",  formata_brl(row["valor_total"]))
    kp2.metric("🎯 Orçamento",  formata_brl(row["orcamento"]) if row.get("orcamento", 0) > 0 else "N/D")
    kp3.metric("💹 Saldo",      formata_brl(saldo_proj) if saldo_proj is not None else "N/D")

    # Linha 2: Horas | Custo/h | Colaboradores
    kp4, kp5, kp6 = st.columns(3)
    kp4.metric("⏱️ Horas",        f"{row['horas_total']:.0f} h")
    kp5.metric("📐 Custo/h",      formata_brl(row["custo_por_hora"]))
    kp6.metric("👥 Colaboradores", str(int(row.get("n_colaboradores", 0))))

    # Barra de consumo de orçamento
    if row.get("orcamento", 0) > 0:
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

    # ── Cronograma ────────────────────────────────────────────────────────────
    st.markdown("#### 📅 Cronograma")
    marcos_html = _tabela_marcos_html(row)
    if marcos_html:
        st.markdown(marcos_html, unsafe_allow_html=True)
    else:
        st.caption("ℹ️ Sem datas cadastradas. Acesse **Orçamentos** para informar.")

    st.divider()

    # ── Gráfico: Distribuição de Horas por Colaborador (com Área) ────────────
    if not df_horas_raw.empty and "c_custo" in df_horas_raw.columns:
        df_h_proj = df_horas_raw[df_horas_raw["c_custo"] == cc]
        if not df_h_proj.empty and "nome" in df_h_proj.columns:
            st.markdown("#### ⏱️ Distribuição de Horas por Colaborador")
            st.plotly_chart(
                charts.grafico_horas_colaborador(df_h_proj, row.get("nome_projeto", cc)),
                use_container_width=True,
            )
            st.divider()

    # ── Gráfico: Evolução Mensal de Desembolsos (área + colunas combinado) ───
    if not df_custos_raw.empty and "centro_de_custo" in df_custos_raw.columns:
        df_c_proj = df_custos_raw[df_custos_raw["centro_de_custo"] == cc]
        if not df_c_proj.empty and "mes_ref" in df_c_proj.columns:
            st.markdown("#### 📈 Evolução Mensal de Desembolsos")
            st.plotly_chart(
                charts.grafico_evolucao_mensal_projeto(
                    df_c_proj, row.get("nome_projeto", cc)
                ),
                use_container_width=True,
            )
