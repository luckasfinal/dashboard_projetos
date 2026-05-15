import sys
from pathlib import Path
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from utils.db import init_db
from utils.data_processor import agregar_tudo, formata_brl, cor_status
from utils import charts

init_db()
st.title("📈 Andamento dos Projetos")

df, df_custos, df_horas = agregar_tudo()

if df.empty:
    st.warning("⚠️ Nenhum dado encontrado. Acesse **Upload de Planilhas** e importe seus arquivos.")
    st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filtros")
    projetos_all = sorted(df["projeto"].unique().tolist())
    projetos_sel = st.multiselect("Centro de Custo / Projeto", projetos_all, default=projetos_all)

    if "segmento" in df.columns:
        segs = sorted(df["segmento"].dropna().unique().tolist())
        segs = [s for s in segs if s and str(s) != "0"]
        if segs:
            seg_sel = st.multiselect("Segmento", segs, default=segs)
            projetos_sel = [p for p in projetos_sel
                            if df.loc[df["projeto"] == p, "segmento"].values[0] in seg_sel]

df_f = df[df["projeto"].isin(projetos_sel)]

# ── Gauges de orçamento (percentual de realizado/orçamento) ──────────────────
st.subheader("Consumo de Orçamento por Projeto")

# Aviso se não houver orçamento cadastrado
tem_orcamento = (df_f["orcamento"] > 0).any()
if not tem_orcamento:
    st.info(
        "ℹ️ As planilhas não contêm coluna de **orçamento**. "
        "Os gauges serão exibidos apenas quando um orçamento for informado. "
        "Por ora, é exibido o realizado absoluto por projeto."
    )
    # Mostra barras de realizado no lugar dos gauges
    st.plotly_chart(charts.grafico_realizado_por_projeto(df_f), use_container_width=True)
else:
    n = len(df_f)
    cols = st.columns(min(n, 4)) if n > 0 else st.columns(1)
    for i, (_, row) in enumerate(df_f.iterrows()):
        with cols[i % len(cols)]:
            st.plotly_chart(
                charts.gauge_orcamento(row["projeto"], row["pct_orcamento"]),
                use_container_width=True,
            )

st.divider()

# ── Cards por centro de custo ─────────────────────────────────────────────────
st.subheader("Detalhamento por Centro de Custo")

for _, row in df_f.iterrows():
    semaforo = cor_status(row["pct_orcamento"]) if row["orcamento"] > 0 else "📋"
    label_extra = ""
    for campo in ["area", "filial", "tipo_projeto", "segmento"]:
        v = row.get(campo, 0)
        if v and str(v) != "0":
            label_extra += f" · {v}"

    with st.expander(f"{semaforo} **{row['projeto']}**{label_extra}", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Realizado",    formata_brl(row["valor_total"]))
        c2.metric("Orçamento",    formata_brl(row["orcamento"]) if row["orcamento"] > 0 else "N/D")
        c3.metric("Horas Totais", f"{row['horas_total']:.0f} h")
        c4.metric("Custo/h",      formata_brl(row["custo_por_hora"]))

        if row["orcamento"] > 0:
            pct = row["pct_orcamento"]
            label_pct = f"{'🚨 ESTOURO — ' if pct > 100 else ''}{pct:.1f}% do orçamento consumido"
            st.markdown(f"**{label_pct}**")
            st.progress(min(pct / 100, 1.0))
            if pct > 100:
                st.error(f"⚠️ Estouro de {formata_brl(abs(row['saldo_orcamento']))} acima do orçamento!")
            elif row["saldo_orcamento"] > 0:
                st.success(f"✅ Saldo disponível: {formata_brl(row['saldo_orcamento'])}")

        st.markdown(
            f"**Colaboradores:** {int(row.get('n_colaboradores', 0))} &nbsp;|&nbsp; "
            f"**Equipe:** {row.get('colaboradores', 'N/D')}"
        )

        # Gráfico de horas por colaborador (nome)
        if not df_horas.empty and "c_custo" in df_horas.columns:
            df_h_proj = df_horas[df_horas["c_custo"] == row["projeto"]]
            if not df_h_proj.empty and "nome" in df_h_proj.columns:
                st.plotly_chart(
                    charts.grafico_horas_colaborador(df_h_proj, row["projeto"]),
                    use_container_width=True,
                )

st.divider()

# ── Tabela de andamento ───────────────────────────────────────────────────────
st.subheader("Tabela de Andamento")

cols_disp = ["projeto", "valor_total", "horas_total", "custo_por_hora"]
if (df_f["orcamento"] > 0).any():
    cols_disp += ["orcamento", "saldo_orcamento", "pct_orcamento"]
for c in ["filial", "area", "segmento"]:
    if c in df_f.columns:
        cols_disp.append(c)

tabela = df_f[cols_disp].copy()

if "pct_orcamento" in tabela.columns:
    tabela.insert(0, "🚦", tabela["pct_orcamento"].apply(cor_status))

rename_map = {
    "projeto":        "Centro de Custo",
    "valor_total":    "Realizado (R$)",
    "horas_total":    "Horas",
    "custo_por_hora": "R$/h",
    "orcamento":      "Orçamento (R$)",
    "saldo_orcamento":"Saldo (R$)",
    "pct_orcamento":  "% Orçamento",
    "filial":         "Filial",
    "area":           "Área",
    "segmento":       "Segmento",
}
tabela.rename(columns=rename_map, inplace=True)

fmt = {
    "Realizado (R$)":  "R$ {:,.2f}",
    "Horas":           "{:.0f}",
    "R$/h":            "R$ {:.2f}",
}
if "Orçamento (R$)" in tabela.columns:
    fmt["Orçamento (R$)"]  = "R$ {:,.2f}"
    fmt["Saldo (R$)"]      = "R$ {:,.2f}"
    fmt["% Orçamento"]     = "{:.1f}%"

def colorir_pct(val):
    try:
        v = float(str(val).replace("%", "").replace(",", ".").strip())
    except Exception:
        return ""
    if v > 100:
        return "background-color: #c0392b; color: white"
    if v >= 90:
        return "background-color: #ffd6d6; color: #7a0000"
    if v >= 70:
        return "background-color: #fff3cd; color: #664d00"
    return "background-color: #d4edda; color: #155724"

styler = tabela.style.format(fmt)
if "% Orçamento" in tabela.columns:
    styler = styler.applymap(colorir_pct, subset=["% Orçamento"])

st.dataframe(styler, use_container_width=True, hide_index=True)
