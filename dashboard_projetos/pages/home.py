import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.db import init_db
from utils.data_processor import (
    agregar_tudo,
    calcular_risco_portfolio,
    detectar_excecoes,
    formata_brl_curto,
    render_selo_dados,
)
from utils.dashboard_executivo import (
    calcular_kpis_home,
    calcular_marcos_vencidos,
    calcular_proximos_marcos,
)

init_db()

hoje = datetime.today().date()

st.title("🏠 Home Executiva")
st.caption(f"Visão consolidada do portfólio · {hoje.strftime('%d/%m/%Y')}")

df_dashboard, df_custos_raw, _ = agregar_tudo()

if df_dashboard.empty:
    st.warning(
        "⚠️ Nenhum dado encontrado. "
        "Acesse **Upload de Arquivos** e importe suas planilhas."
    )
    st.stop()

render_selo_dados(df_dashboard)

risco = calcular_risco_portfolio(df_dashboard, df_custos_raw)
kpis  = calcular_kpis_home(df_dashboard, risco)

# ── KPIs ──────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📁 Projetos", kpis["n_ativos"])
c2.metric(
    "🔴 Em risco alto",
    kpis["n_alto_risco"],
    help="Projetos com projeção de custo acima do orçamento ou com atraso em algum marco.",
)
c3.metric(
    "💸 Exposição financeira",
    formata_brl_curto(kpis["exposicao_financeira"])
    if kpis["exposicao_financeira"] > 0
    else "R$ 0",
    help="Soma dos valores projetados de estouro de orçamento nos projetos em risco.",
)
c4.metric(
    "📊 Consumo médio",
    f"{kpis['consumo_medio_pct']:.0f}%",
    help="Percentual médio do orçamento já consumido nos projetos com orçamento cadastrado.",
)
c5.metric(
    "⏰ Atraso médio",
    f"{kpis['atraso_medio_dias']:.0f} d",
    help="Média de dias de atraso no marco mais crítico de cada projeto em risco.",
)

st.divider()

# ── Pontos de atenção ─────────────────────────────────────────────────
st.subheader("⚡ Pontos de Atenção")

exc = detectar_excecoes(df_dashboard)

cartoes = []
if exc.get("estouro"):
    cartoes.append(("🚨", len(exc["estouro"]), "acima do orçamento", "#dc2626"))
if exc.get("atrasados"):
    cartoes.append(("⏰", len(exc["atrasados"]), "com lançamento atrasado", "#f59e0b"))
if exc.get("stand_by"):
    cartoes.append(("⏸️", len(exc["stand_by"]), "em Stand by", "#a78bfa"))
if exc.get("cancelados"):
    cartoes.append(("✖️", len(exc["cancelados"]), "cancelados", "#94a3b8"))

if not cartoes:
    st.success("✅ Nenhuma exceção detectada — todos os projetos dentro do previsto.")
else:
    cols_c = st.columns(len(cartoes))
    for col, (icone, n, rotulo, cor) in zip(cols_c, cartoes):
        col.markdown(
            f"""<div style="border:1px solid {cor}55;background:{cor}15;border-radius:10px;
                padding:12px 14px;text-align:center">
                <div style="font-size:22px;font-weight:800;color:{cor}">{icone} {n}</div>
                <div style="font-size:12px;opacity:.8;margin-top:2px">{rotulo}</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown("")

# Projetos em alto risco com deep-link para detalhamento
if not risco.empty:
    alto_risco = risco[risco["nivel_risco"] == "alto"]
    if not alto_risco.empty:
        with st.expander(f"🔴 {len(alto_risco)} projeto(s) em alto risco — ver detalhes"):
            for _, r in alto_risco.iterrows():
                pct_s = (
                    f"{r['pct_projetado']:.0f}% do orçamento"
                    if pd.notna(r.get("pct_projetado"))
                    else "sem orçamento"
                )
                atr_s = (
                    f"{int(r['dias_atraso_max'])}d de atraso"
                    if r["dias_atraso_max"] > 0
                    else "no prazo"
                )
                _cn, _cb = st.columns([4, 1])
                _cn.markdown(f"**{r['nome_projeto']}** — 💰 {pct_s} · ⏰ {atr_s}")
                if _cb.button("Abrir →", key=f"home_ver_{r['projeto']}", use_container_width=True):
                    st.session_state["ir_para_projeto"] = r["projeto"]
                    st.session_state["ir_para_tab"] = "🔍 Detalhamento"
                    st.switch_page(str(_ROOT / "pages" / "3_projetos.py"))

st.divider()

# ── Próximos marcos (7 dias) ──────────────────────────────────────────
st.subheader("📅 Próximos marcos — 7 dias")
df_prox = calcular_proximos_marcos(df_dashboard, dias=7)
if df_prox.empty:
    st.caption("ℹ️ Nenhum marco previsto para os próximos 7 dias.")
else:
    st.dataframe(df_prox, use_container_width=True, hide_index=True)

# ── Marcos vencidos sem conclusão ─────────────────────────────────────
st.subheader("⏰ Marcos vencidos sem conclusão")
df_venc = calcular_marcos_vencidos(df_dashboard)
if df_venc.empty:
    st.success("✅ Nenhum marco com data passada sem conclusão registrada.")
else:
    st.dataframe(df_venc, use_container_width=True, hide_index=True)

st.divider()

# ── Saúde do portfólio ────────────────────────────────────────────────
st.subheader("🎯 Saúde do Portfólio")
s1, s2, s3 = st.columns(3)
s1.metric("🔴 Alto risco",  kpis["n_alto_risco"])
s2.metric("🟡 Risco médio", kpis["n_medio_risco"])
s3.metric("🟢 Baixo risco", kpis["n_baixo_risco"])

st.divider()

# ── Navegação rápida ──────────────────────────────────────────────────
st.subheader("🔗 Navegação Rápida")
n1, n2, n3, n4 = st.columns(4)
if n1.button("🧭 Visão Executiva",      use_container_width=True, type="secondary"):
    st.switch_page(str(_ROOT / "pages" / "4_visao_executiva.py"))
if n2.button("📋 Dashboard Executivo",  use_container_width=True, type="secondary"):
    st.switch_page(str(_ROOT / "pages" / "5_dashboard_executivo.py"))
if n3.button("📊 Dashboard Financeiro", use_container_width=True, type="secondary"):
    st.switch_page(str(_ROOT / "pages" / "2_dashboard.py"))
if n4.button("📈 Andamento dos Projetos", use_container_width=True, type="secondary"):
    st.switch_page(str(_ROOT / "pages" / "3_projetos.py"))
