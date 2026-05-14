import pages._pathfix
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

with st.sidebar:
    st.header("🔍 Filtros")
    projetos_all = sorted(df["projeto"].unique().tolist())
    projetos_sel = st.multiselect("Projetos", projetos_all, default=projetos_all)

df_f = df[df["projeto"].isin(projetos_sel)]

st.subheader("Consumo de Orçamento por Projeto")
n = len(df_f)
cols = st.columns(min(n, 4)) if n > 0 else st.columns(1)
for i, (_, row) in enumerate(df_f.iterrows()):
    with cols[i % len(cols)]:
        st.plotly_chart(charts.gauge_orcamento(row["projeto"], row["pct_orcamento"]), use_container_width=True)

st.divider()
st.subheader("Detalhamento por Projeto")
for _, row in df_f.iterrows():
    semaforo = cor_status(row["pct_orcamento"])
    with st.expander(f"{semaforo} **{row['projeto']}** — {row.get('status', 'N/D')}", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Custo realizado", formata_brl(row["valor_total"]))
        c2.metric("Orçamento",       formata_brl(row["orcamento"]))
        c3.metric("Saldo",           formata_brl(row["saldo_orcamento"]),
                  delta_color="normal" if row["saldo_orcamento"] >= 0 else "inverse")
        c4.metric("Horas totais",    f"{row['horas_total']:.0f} h")
        st.markdown(f"**% orçamento consumido:** {row['pct_orcamento']:.1f}%")
        st.progress(int(row["pct_orcamento"]) / 100)
        st.markdown(
            f"**Custo/hora:** {formata_brl(row['custo_por_hora'])}/h &nbsp;|&nbsp; "
            f"**Colaboradores:** {int(row['n_colaboradores'])} &nbsp;|&nbsp; "
            f"**Equipe:** {row.get('colaboradores', 'N/D')}"
        )
        if not df_horas.empty:
            df_h_proj = df_horas[df_horas["projeto"] == row["projeto"]]
            if not df_h_proj.empty:
                st.plotly_chart(charts.grafico_horas_colaborador(df_h_proj, row["projeto"]), use_container_width=True)

st.divider()
st.subheader("Tabela de Andamento")
tabela = df_f[["projeto","valor_total","orcamento","saldo_orcamento",
               "horas_total","custo_por_hora","pct_orcamento","status"]].copy()
tabela.insert(0, "🚦", tabela["pct_orcamento"].apply(cor_status))
tabela.columns = ["🚦","Projeto","Custo (R$)","Orçamento (R$)","Saldo (R$)","Horas","R$/h","% Orçamento","Status"]
st.dataframe(
    tabela.style.format({
        "Custo (R$)":     "R$ {:,.2f}",
        "Orçamento (R$)": "R$ {:,.2f}",
        "Saldo (R$)":     "R$ {:,.2f}",
        "Horas":          "{:.0f}",
        "R$/h":           "R$ {:.2f}",
        "% Orçamento":    "{:.1f}%",
    }).background_gradient(subset=["% Orçamento"], cmap="RdYlGn_r"),
    use_container_width=True, hide_index=True,
)
