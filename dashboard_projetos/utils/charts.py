import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Paleta consistente
CORES = px.colors.qualitative.Set2

LAYOUT_BASE = dict(
    font_family="Inter, sans-serif",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def grafico_custo_vs_orcamento(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Custo realizado",
        x=df["projeto"],
        y=df["valor_total"],
        marker_color="#4C78A8",
        text=[f"R$ {v:,.0f}" for v in df["valor_total"]],
        textposition="auto",
    ))
    fig.add_trace(go.Bar(
        name="Orçamento",
        x=df["projeto"],
        y=df["orcamento"],
        marker_color="#F58518",
        opacity=0.6,
        text=[f"R$ {v:,.0f}" for v in df["orcamento"]],
        textposition="auto",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="Custo Realizado vs Orçamento",
        barmode="group",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
    )
    return fig


def grafico_horas_por_projeto(df: pd.DataFrame) -> go.Figure:
    fig = px.bar(
        df.sort_values("horas_total", ascending=True),
        x="horas_total",
        y="projeto",
        orientation="h",
        color="horas_total",
        color_continuous_scale="Blues",
        text="horas_total",
        title="Horas por Projeto",
    )
    fig.update_traces(texttemplate="%{text:.0f} h", textposition="outside")
    fig.update_layout(**LAYOUT_BASE, coloraxis_showscale=False)
    return fig


def grafico_custo_por_hora(df: pd.DataFrame) -> go.Figure:
    df_plot = df[df["custo_por_hora"] > 0].sort_values("custo_por_hora", ascending=False)
    fig = px.bar(
        df_plot,
        x="projeto",
        y="custo_por_hora",
        color="projeto",
        color_discrete_sequence=CORES,
        text=[f"R$ {v:.2f}" for v in df_plot["custo_por_hora"]],
        title="Custo por Hora (R$/h)",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(**LAYOUT_BASE, showlegend=False, yaxis_tickprefix="R$ ")
    return fig


def grafico_pizza_categorias(df_custos: pd.DataFrame) -> go.Figure:
    if "categoria" not in df_custos.columns:
        return go.Figure()
    agg = df_custos.groupby("categoria")["valor"].sum().reset_index()
    fig = px.pie(
        agg,
        names="categoria",
        values="valor",
        title="Distribuição de Custos por Categoria",
        color_discrete_sequence=CORES,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(**LAYOUT_BASE)
    return fig


def grafico_evolucao_mensal(df_custos: pd.DataFrame, df_horas: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if "mes" in df_custos.columns:
        custo_mes = df_custos.groupby("mes")["valor"].sum().reset_index().sort_values("mes")
        fig.add_trace(go.Scatter(
            x=custo_mes["mes"], y=custo_mes["valor"],
            name="Custo (R$)", mode="lines+markers",
            line=dict(color="#4C78A8", width=2),
            yaxis="y1",
        ))

    if "mes" in df_horas.columns:
        horas_mes = df_horas.groupby("mes")["horas"].sum().reset_index().sort_values("mes")
        fig.add_trace(go.Scatter(
            x=horas_mes["mes"], y=horas_mes["horas"],
            name="Horas", mode="lines+markers",
            line=dict(color="#F58518", width=2, dash="dot"),
            yaxis="y2",
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title="Evolução Mensal — Custos e Horas",
        yaxis=dict(title="Custo (R$)", tickprefix="R$ ", tickformat=",.0f"),
        yaxis2=dict(title="Horas", overlaying="y", side="right"),
    )
    return fig


def gauge_orcamento(projeto: str, pct: float) -> go.Figure:
    cor = "#e74c3c" if pct >= 90 else "#f39c12" if pct >= 70 else "#2ecc71"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": "%", "font": {"size": 22}},
        title={"text": projeto, "font": {"size": 13}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": cor},
            "steps": [
                {"range": [0, 70],  "color": "#eafaf1"},
                {"range": [70, 90], "color": "#fef9e7"},
                {"range": [90, 100], "color": "#fdedec"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 3},
                "thickness": 0.75,
                "value": 100,
            },
        },
    ))
    fig.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10),
                      paper_bgcolor="rgba(0,0,0,0)")
    return fig


def grafico_horas_colaborador(df_horas: pd.DataFrame, projeto: str | None = None) -> go.Figure:
    df = df_horas.copy()
    if projeto:
        df = df[df["projeto"] == projeto]
    if "colaborador" not in df.columns:
        return go.Figure()
    agg = df.groupby("colaborador")["horas"].sum().reset_index().sort_values("horas", ascending=True)
    fig = px.bar(
        agg, x="horas", y="colaborador", orientation="h",
        color="horas", color_continuous_scale="Teal",
        text="horas",
        title=f"Horas por Colaborador{f' — {projeto}' if projeto else ''}",
    )
    fig.update_traces(texttemplate="%{text:.0f} h", textposition="outside")
    fig.update_layout(**LAYOUT_BASE, coloraxis_showscale=False)
    return fig
