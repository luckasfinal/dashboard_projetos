import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

CORES = px.colors.qualitative.Set2

LAYOUT_BASE = dict(
    font_family="Inter, sans-serif",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def grafico_realizado_por_projeto(df: pd.DataFrame) -> go.Figure:
    """Barras de realizado por centro de custo (sem orçamento)."""
    df_plot = df.sort_values("valor_total", ascending=False).head(20)
    fig = go.Figure(go.Bar(
        x=df_plot["projeto"],
        y=df_plot["valor_total"],
        marker_color="#4C78A8",
        text=[f"R$ {v:,.0f}" for v in df_plot["valor_total"]],
        textposition="auto",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="Realizado por Centro de Custo (Top 20)",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
    )
    return fig


def grafico_custo_vs_orcamento(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Realizado",
        x=df["projeto"], y=df["valor_total"],
        marker_color="#4C78A8",
        text=[f"R$ {v:,.0f}" for v in df["valor_total"]],
        textposition="auto",
    ))
    if (df["orcamento"] > 0).any():
        fig.add_trace(go.Bar(
            name="Orçamento",
            x=df["projeto"], y=df["orcamento"],
            marker_color="#F58518", opacity=0.6,
            text=[f"R$ {v:,.0f}" for v in df["orcamento"]],
            textposition="auto",
        ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="Realizado vs Orçamento",
        barmode="group",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
    )
    return fig


def grafico_horas_por_projeto(df: pd.DataFrame) -> go.Figure:
    df_plot = df.sort_values("horas_total", ascending=True).tail(20)
    fig = px.bar(
        df_plot, x="horas_total", y="projeto", orientation="h",
        color="horas_total", color_continuous_scale="Blues",
        text="horas_total",
        title="Horas por Centro de Custo (Top 20)",
    )
    fig.update_traces(texttemplate="%{text:.0f} h", textposition="outside")
    fig.update_layout(**LAYOUT_BASE, coloraxis_showscale=False)
    return fig


def grafico_custo_por_hora(df: pd.DataFrame) -> go.Figure:
    df_plot = df[df["custo_por_hora"] > 0].sort_values("custo_por_hora", ascending=False).head(20)
    fig = px.bar(
        df_plot, x="projeto", y="custo_por_hora",
        color="projeto", color_discrete_sequence=CORES,
        text=[f"R$ {v:.2f}" for v in df_plot["custo_por_hora"]],
        title="Custo por Hora R$/h (Top 20)",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(**LAYOUT_BASE, showlegend=False, yaxis_tickprefix="R$ ")
    return fig


def grafico_pizza_conta(df_custos: pd.DataFrame) -> go.Figure:
    """Distribuição de custos por conta contábil."""
    if "conta" not in df_custos.columns:
        return go.Figure()
    agg = df_custos.groupby("conta")["realizado"].sum().reset_index()
    fig = px.pie(
        agg, names="conta", values="realizado",
        title="Distribuição por Conta Contábil",
        color_discrete_sequence=CORES,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(**LAYOUT_BASE)
    return fig


def grafico_pizza_categorias(df_custos: pd.DataFrame) -> go.Figure:
    """Mantido para compatibilidade — usa conta se categoria não existir."""
    col = "categoria" if "categoria" in df_custos.columns else (
          "conta"     if "conta"     in df_custos.columns else None)
    val = "realizado" if "realizado" in df_custos.columns else "valor"
    if not col or val not in df_custos.columns:
        return go.Figure()
    agg = df_custos.groupby(col)[val].sum().reset_index()
    fig = px.pie(agg, names=col, values=val,
                 title="Distribuição de Custos",
                 color_discrete_sequence=CORES)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(**LAYOUT_BASE)
    return fig


def grafico_evolucao_mensal(df_custos: pd.DataFrame,
                             df_horas: pd.DataFrame,
                             mes_col: str = "mes_ref") -> go.Figure:
    fig = go.Figure()
    val_col = "realizado" if "realizado" in df_custos.columns else "valor"

    if mes_col in df_custos.columns and val_col in df_custos.columns:
        custo_mes = (df_custos.groupby(mes_col)[val_col].sum()
                     .reset_index().sort_values(mes_col))
        fig.add_trace(go.Scatter(
            x=custo_mes[mes_col], y=custo_mes[val_col],
            name="Realizado (R$)", mode="lines+markers",
            line=dict(color="#4C78A8", width=2), yaxis="y1",
        ))

    if mes_col in df_horas.columns and "hs_nor" in df_horas.columns:
        horas_mes = (df_horas.groupby(mes_col)["hs_nor"].sum()
                     .reset_index().sort_values(mes_col))
        fig.add_trace(go.Scatter(
            x=horas_mes[mes_col], y=horas_mes["hs_nor"],
            name="Horas", mode="lines+markers",
            line=dict(color="#F58518", width=2, dash="dot"), yaxis="y2",
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title="Evolução Mensal — Realizado e Horas",
        yaxis=dict(title="Realizado (R$)", tickprefix="R$ ", tickformat=",.0f"),
        yaxis2=dict(title="Horas", overlaying="y", side="right"),
    )
    return fig


def gauge_orcamento(projeto: str, pct: float) -> go.Figure:
    """
    Gauge que suporta valores acima de 100% (estouro de orçamento).
    O eixo se expande dinamicamente para acomodar o valor real.
    """
    max_val = max(120, pct + 10) if pct > 100 else 120

    if pct > 100:
        cor_bar = "#c0392b"       # vermelho escuro — estouro
    elif pct >= 90:
        cor_bar = "#e74c3c"       # vermelho
    elif pct >= 70:
        cor_bar = "#f39c12"       # amarelo
    else:
        cor_bar = "#2ecc71"       # verde

    steps = [
        {"range": [0, 70],       "color": "#eafaf1"},
        {"range": [70, 90],      "color": "#fef9e7"},
        {"range": [90, 100],     "color": "#fdedec"},
    ]
    if max_val > 100:
        steps.append({"range": [100, max_val], "color": "#f5b7b1"})

    titulo = projeto
    if pct > 100:
        titulo += "<br><span style='color:#c0392b;font-size:11px'>⚠️ ESTOURO</span>"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number={"suffix": "%", "font": {"size": 20},
                "valueformat": ".1f"},
        delta={"reference": 100, "relative": False,
               "valueformat": ".1f",
               "suffix": "pp",
               "increasing": {"color": "#c0392b"},
               "decreasing": {"color": "#2ecc71"}},
        title={"text": titulo, "font": {"size": 12}},
        gauge={
            "axis": {"range": [0, max_val], "tickwidth": 1,
                     "tickvals": [0, 25, 50, 75, 100] + ([max_val] if pct > 100 else [])},
            "bar":  {"color": cor_bar},
            "steps": steps,
            "threshold": {
                "line": {"color": "red", "width": 3},
                "thickness": 0.75,
                "value": 100,
            },
        },
    ))
    fig.update_layout(
        height=220,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def grafico_horas_colaborador(df_horas: pd.DataFrame,
                               projeto: str | None = None) -> go.Figure:
    df = df_horas.copy()
    col_nome = "nome" if "nome" in df.columns else (
               "colaborador" if "colaborador" in df.columns else None)
    col_h    = "hs_nor" if "hs_nor" in df.columns else (
               "horas"  if "horas"  in df.columns else None)
    if not col_nome or not col_h:
        return go.Figure()

    agg = df.groupby(col_nome)[col_h].sum().reset_index().sort_values(col_h, ascending=True)
    titulo = f"Horas por Colaborador{f' — {projeto}' if projeto else ''}"
    fig = px.bar(
        agg, x=col_h, y=col_nome, orientation="h",
        color=col_h, color_continuous_scale="Teal",
        text=col_h, title=titulo,
    )
    fig.update_traces(texttemplate="%{text:.0f} h", textposition="outside")
    fig.update_layout(**LAYOUT_BASE, coloraxis_showscale=False)
    return fig
