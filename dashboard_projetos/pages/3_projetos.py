import sys
from pathlib import Path
from datetime import datetime
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
from utils.db import init_db
from utils.data_processor import (
    agregar_tudo, formata_brl, cor_status, cor_status_projeto,
    badge_status_projeto, agrupar_por_nome_projeto,
)
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
.marco-nome  { flex:2; font-size:13px; }
.marco-data  { flex:1.1; font-size:13px; font-weight:600; text-align:center; }
.marco-badge { flex:1.3; text-align:center; font-size:12px; font-weight:700;
               border-radius:20px; padding:3px 10px; }
.marco-tend  { flex:1.3; text-align:center; font-size:12px; font-weight:700;
               border-radius:20px; padding:3px 10px; }
.badge-ok        { background:rgba(22,163,74,.25);  color:#4ade80; }
.badge-atrasado  { background:rgba(220,38,38,.25);  color:#f87171; }
.badge-pendente  { background:rgba(234,179,8,.2);   color:#fbbf24; }
.badge-futuro    { background:rgba(99,102,241,.2);  color:#a5b4fc; }
.badge-vazio     { background:rgba(128,128,128,.12);color:rgba(128,128,128,.5); }

/* Consumo de orçamento — barras compactas */
.consumo-row {
    display:flex; align-items:center; gap:10px; padding:8px 0;
    border-bottom:1px solid rgba(128,128,128,.1);
}
.consumo-nome { flex:2.2; font-size:13px; font-weight:600; }
.consumo-status { flex:1.8; text-align:left; }
.consumo-bar-wrap { flex:3; background:rgba(128,128,128,.18); border-radius:6px; height:10px; overflow:hidden; }
.consumo-bar { height:100%; border-radius:6px; }
.consumo-pct { flex:0.8; text-align:right; font-size:13px; font-weight:700; white-space:nowrap; }
.consumo-val { flex:1.6; text-align:right; font-size:12px; opacity:.7; white-space:nowrap; }
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
lista_status   = sorted(df["status_projeto"].dropna().unique().tolist()) if "status_projeto" in df.columns else []

if "filtro_projetos" not in st.session_state: st.session_state["filtro_projetos"] = lista_projetos
if "filtro_anos"     not in st.session_state: st.session_state["filtro_anos"]     = lista_anos
if "filtro_meses"    not in st.session_state: st.session_state["filtro_meses"]    = lista_meses
if "filtro_status"   not in st.session_state: st.session_state["filtro_status"]   = lista_status

st.session_state["filtro_projetos"] = [p for p in st.session_state["filtro_projetos"] if p in lista_projetos]
st.session_state["filtro_anos"]     = [a for a in st.session_state["filtro_anos"]     if a in lista_anos]
st.session_state["filtro_meses"]    = [m for m in st.session_state["filtro_meses"]    if m in lista_meses]
st.session_state["filtro_status"]   = [s for s in st.session_state["filtro_status"]   if s in lista_status]

with st.sidebar:
    st.header("🔍 Filtros")
    projetos_selecionados = st.multiselect("Projetos:", options=lista_projetos,
        default=st.session_state["filtro_projetos"], key="filtro_projetos")
    anos_selecionados = st.multiselect("Ano:", options=lista_anos,
        default=st.session_state["filtro_anos"], key="filtro_anos")
    meses_selecionados = st.multiselect("Mês:", options=lista_meses,
        default=st.session_state["filtro_meses"], key="filtro_meses")
    status_selecionados = st.multiselect("Status do Projeto:", options=lista_status,
        default=st.session_state["filtro_status"], key="filtro_status")
    if st.button("🔄 Limpar filtros", use_container_width=True):
        st.session_state["filtro_projetos"] = lista_projetos
        st.session_state["filtro_anos"]     = lista_anos
        st.session_state["filtro_meses"]    = lista_meses
        st.session_state["filtro_status"]   = lista_status
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
if status_selecionados and "status_projeto" in df_f.columns:
    df_f = df_f[df_f["status_projeto"].isin(status_selecionados)]

if df_f.empty:
    st.info("Nenhum projeto encontrado para os filtros selecionados.")
    st.stop()

tem_orc = (df_f.get("orcamento", pd.Series([0])) > 0).any()
hoje    = datetime.today().date()

# ── Helpers de data ───────────────────────────────────────────────────────────
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

def _tendencia(col_prev, col_real, prev_d, real_d) -> str:
    """
    Calcula a Tendência entre previsto e realizado de um marco:
      - "-"                    : dados insuficientes para o cálculo
      - "No prazo"             : realizado <= previsto
      - "Em atraso (x dias)"    : realizado > previsto, x dias de atraso
    Para marcos sem 'realizado' (ex: Início CC), retorna "-".
    """
    if col_real is None:
        return "-"
    if not prev_d or not real_d:
        return "-"
    diff = (real_d - prev_d).days
    if diff <= 0:
        return "No prazo"
    return f"Em atraso ({diff} dias)"

def _badge_tendencia(tendencia: str) -> str:
    if tendencia == "-":
        return "<span class='marco-tend badge-vazio'>-</span>"
    if tendencia == "No prazo":
        return "<span class='marco-tend badge-ok'>No prazo</span>"
    return f"<span class='marco-tend badge-atrasado'>{tendencia}</span>"

MARCOS_DEF = [
    ("data_inicio",           None,                   "Início CC"),
    ("prev_viabilidade",      "real_viabilidade",     "Viabilidade"),
    ("prev_qualidade",        "real_qualidade",       "Qualidade"),
    ("prev_aprov_lancamento", "real_aprov_lancamento","Aprov. Lançamento"),
    ("prev_lancamento",       "real_lancamento",      "Lançamento"),
]

def _tabela_marcos_html(row) -> str:
    """Tabela de cronograma com colunas: Marco | Previsto | Realizado | Situação | Tendência."""
    html = """
    <div class='marco-header'>
        <div class='marco-nome'>Marco</div>
        <div class='marco-data'>Previsto</div>
        <div class='marco-data'>Realizado</div>
        <div class='marco-badge'>Situação</div>
        <div class='marco-tend'>Tendência</div>
    </div>"""
    tem = False
    for col_prev, col_real, nome in MARCOS_DEF:
        prev_d = _parse(row.get(col_prev))
        real_d = _parse(row.get(col_real)) if col_real else None
        if not prev_d and not real_d:
            continue
        tem = True
        tendencia = _tendencia(col_prev, col_real, prev_d, real_d)
        html += f"""
        <div class='marco-row'>
            <div class='marco-nome'>{nome}</div>
            <div class='marco-data'>{prev_d.strftime('%d/%m/%Y') if prev_d else '—'}</div>
            <div class='marco-data'>{real_d.strftime('%d/%m/%Y') if real_d else '—'}</div>
            {_badge(col_prev, col_real, prev_d, real_d)}
            {_badge_tendencia(tendencia)}
        </div>"""
    return html if tem else ""

# ═══════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════
tab_resumo, tab_detalhe = st.tabs(["📊 Resumo Geral", "🔍 Detalhamento"])

# ───────────────────────────────────────────────────────────────────
# TAB 1 — RESUMO GERAL (conciso, sem gauges)
# ───────────────────────────────────────────────────────────────────
with tab_resumo:
    total_custo   = df_f["valor_total"].sum()
    total_horas   = df_f["horas_total"].sum()
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

    # Linha 1: Orçamento Total | Realizado Total | Saldo Consolidado
    r1c1, r1c2, r1c3 = st.columns(3)
    r1c1.metric("🎯 Orçamento Total",  formata_brl(total_orc) if tem_orc else "Não cadastrado")
    r1c2.metric("💰 Realizado Total",  formata_brl(total_custo))
    r1c3.metric("💹 Saldo Consolidado",
                formata_brl(saldo_total) if saldo_total is not None else "N/D",
                delta=f"{pct_cons:.1f}% consumido" if pct_cons else None,
                delta_color="inverse")

    # Linha 2: Projetos Ativos | Horas Totais | Com Atraso
    r2c1, r2c2, r2c3 = st.columns(3)
    r2c1.metric("📁 Projetos Ativos", str(n_proj))
    r2c2.metric("⏱️ Horas Totais",    f"{total_horas:,.0f} h")
    r2c3.metric("⚠️ Com Atraso",      str(n_atrasados))

    st.markdown("")
    st.divider()

    # ── Nova visualização: Consumo de Orçamento — barras horizontais compactas ──
    if tem_orc:
        st.subheader("💳 Consumo de Orçamento por Projeto")

        df_consumo = df_f[df_f["orcamento"] > 0].sort_values("pct_orcamento", ascending=False)

        if df_consumo.empty:
            st.caption("Nenhum projeto com orçamento cadastrado nos filtros atuais.")
        else:
            # Cabeçalho das colunas
            st.markdown("""
            <div class='consumo-row' style='border-bottom:2px solid rgba(128,128,128,.3);
                 font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;opacity:.6'>
                <div class='consumo-nome'>Projeto</div>
                <div class='consumo-status'>Status</div>
                <div class='consumo-bar-wrap' style='background:transparent'>Consumo</div>
                <div class='consumo-pct'>%</div>
                <div class='consumo-val'>Realizado / Orçado</div>
            </div>""", unsafe_allow_html=True)
            for _, row in df_consumo.iterrows():
                pct = row["pct_orcamento"]
                cor = "#dc2626" if pct > 100 else ("#f59e0b" if pct >= 80 else "#22c55e")
                nome_proj = row.get("nome_projeto", row["projeto"])
                status_proj = row.get("status_projeto", "")
                badge = badge_status_projeto(status_proj) if status_proj else ""
                largura = min(pct, 100)
                alerta = " 🚨" if pct > 100 else ""
                st.markdown(f"""
                <div class='consumo-row'>
                    <div class='consumo-nome'>{nome_proj}</div>
                    <div class='consumo-status'>{badge}</div>
                    <div class='consumo-bar-wrap'>
                        <div class='consumo-bar' style='width:{largura:.1f}%;background:{cor}'></div>
                    </div>
                    <div class='consumo-pct' style='color:{cor}'>{pct:.1f}%{alerta}</div>
                    <div class='consumo-val'>{formata_brl(row['valor_total'])} / {formata_brl(row['orcamento'])}</div>
                </div>""", unsafe_allow_html=True)
    else:
        st.plotly_chart(charts.grafico_realizado_por_projeto(df_f),
                        use_container_width=True, key="grafico_realizado_resumo")

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
            "Status":           row.get("status_projeto", "—"),
            "Realizado":        formata_brl(row["valor_total"]),
            "Orçamento":        formata_brl(row["orcamento"]) if tem_orc and row.get("orcamento", 0) > 0 else "N/D",
            "% Orç.":           f"{pct:.0f}%" if tem_orc and pct else "—",
            "Horas":            f"{row['horas_total']:.0f} h",
            "Início CC":        _fmt(row.get("data_inicio")),
            "Lançamento Prev.": _fmt(row.get("prev_lancamento")),
            "Status Lanç.":     _status_lanc(row),
        })

    st.dataframe(pd.DataFrame(rows_st), use_container_width=True, hide_index=True)
    col_dl, _ = st.columns([1, 4])
    col_dl.download_button("⬇️ Exportar CSV",
        pd.DataFrame(rows_st).to_csv(index=False).encode("utf-8"),
        "status_projetos.csv", "text/csv")

# ───────────────────────────────────────────────────────────────────
# TAB 2 — DETALHAMENTO (agrupado por nome do projeto, sem o CC)
# ───────────────────────────────────────────────────────────────────
with tab_detalhe:
    st.subheader("🔍 Detalhamento por Projeto")
    st.caption(
        "Projetos com o mesmo nome (ignorando o código de Centro de Custo) "
        "são agrupados em um único item."
    )

    # Agrupamento: ignora os 9 dígitos do CC no início do nome_projeto
    df_grp = agrupar_por_nome_projeto(df_f)

    proj_opcoes = df_grp["nome_projeto"].tolist()

    projeto_detalhe = st.selectbox(
        "Selecione um projeto:",
        options=proj_opcoes,
    )

    row = df_grp[df_grp["nome_projeto"] == projeto_detalhe].iloc[0]
    cc  = row["projeto"]  # pode ser "100150268, 100150311" se agrupado

    # Header do projeto
    extras = " · ".join(
        str(row.get(c, "")) for c in ["filial", "area", "segmento"]
        if row.get(c, "") not in ("", "0", 0)
    )
    status_proj = row.get("status_projeto", "")
    st.markdown(f"""
    <div style="background:linear-gradient(90deg,rgba(37,99,235,.6),rgba(37,99,235,.25));
                border:1px solid rgba(37,99,235,.4);border-radius:12px;
                padding:16px 22px;margin:10px 0 18px">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">
            <div>
                <div style="font-size:19px;font-weight:700">{row['nome_projeto']}</div>
                <div style="font-size:12px;opacity:.7;margin-top:4px">
                    CC: {cc}{(' · ' + extras) if extras else ''}
                </div>
            </div>
            <div>{badge_status_projeto(status_proj) if status_proj else ''}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── KPIs do projeto — 6 indicadores em 2 linhas ──────────────────────────
    saldo_proj = row.get("saldo_orcamento", 0) if row.get("orcamento", 0) > 0 else None

    kp1, kp2, kp3 = st.columns(3)
    kp1.metric("💰 Realizado",  formata_brl(row["valor_total"]))
    kp2.metric("🎯 Orçamento",  formata_brl(row["orcamento"]) if row.get("orcamento", 0) > 0 else "N/D")
    kp3.metric("💹 Saldo",      formata_brl(saldo_proj) if saldo_proj is not None else "N/D")

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

    # ── Cronograma com coluna Tendência ──────────────────────────────────────
    st.markdown("#### 📅 Cronograma")
    marcos_html = _tabela_marcos_html(row)
    if marcos_html:
        st.markdown(marcos_html, unsafe_allow_html=True)
        st.caption(
            "**Tendência**: \"No prazo\" se o realizado ocorreu até a data prevista; "
            "\"Em atraso (x dias)\" indica quantos dias após o previsto; "
            "\"-\" quando não há dados suficientes para o cálculo."
        )
    else:
        st.caption("ℹ️ Sem datas cadastradas. Acesse **Orçamentos** para informar.")

    st.divider()

    # ── Gráfico: Distribuição de Horas por Colaborador (com Área) ────────────
    # Para projetos agrupados (múltiplos CCs), filtra por todos os CCs do grupo
    ccs_grupo = [c.strip() for c in str(cc).split(",")]

    if not df_horas_raw.empty and "c_custo" in df_horas_raw.columns:
        df_h_proj = df_horas_raw[df_horas_raw["c_custo"].isin(ccs_grupo)]
        if not df_h_proj.empty and "nome" in df_h_proj.columns:
            st.markdown("#### ⏱️ Distribuição de Horas por Colaborador")
            st.plotly_chart(
                charts.grafico_horas_colaborador(df_h_proj, row.get("nome_projeto", cc)),
                use_container_width=True,
                key=f"horas_colab_{cc}",
            )
            st.divider()

    # ── Gráfico: Evolução Mensal de Desembolsos (área + colunas combinado) ───
    if not df_custos_raw.empty and "centro_de_custo" in df_custos_raw.columns:
        df_c_proj = df_custos_raw[df_custos_raw["centro_de_custo"].isin(ccs_grupo)]
        if not df_c_proj.empty and "mes_ref" in df_c_proj.columns:
            st.markdown("#### 📈 Evolução Mensal de Desembolsos")
            st.plotly_chart(
                charts.grafico_evolucao_mensal_projeto(
                    df_c_proj, row.get("nome_projeto", cc)
                ),
                use_container_width=True,
                key=f"evolucao_mensal_{cc}",
            )
