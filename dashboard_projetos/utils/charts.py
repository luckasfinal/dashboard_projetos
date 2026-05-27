import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

CORES = ["#2563eb","#16a34a","#d97706","#dc2626","#7c3aed","#0891b2","#be185d","#65a30d"]

LAYOUT_BASE = dict(
    font_family="Inter, sans-serif",
    font_size=12,
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=44, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hoverlabel=dict(font_size=12),
)

def _titulo(texto: str) -> dict:
    return dict(text=f"<b>{texto}</b>", font=dict(size=14))


def grafico_realizado_por_projeto(df: pd.DataFrame) -> go.Figure:
    # usa nome_projeto se disponível, senão CC
    eixo_x = "nome_projeto" if "nome_projeto" in df.columns else "projeto"
    df_plot = df.sort_values("valor_total", ascending=False).head(20)
    fig = go.Figure(go.Bar(
        x=df_plot[eixo_x],
        y=df_plot["valor_total"],
        marker_color=CORES[0],
        marker_line_width=0,
        text=[f"R$ {v:,.0f}" for v in df_plot["valor_total"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Realizado: R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title=_titulo("Realizado por Projeto"),
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(128,128,128,.15)"),
        xaxis=dict(tickangle=-30),
    )
    return fig


def grafico_custo_vs_orcamento(df: pd.DataFrame) -> go.Figure:
    eixo_x  = "nome_projeto" if "nome_projeto" in df.columns else "projeto"
    df_plot = df.sort_values("valor_total", ascending=False).head(20)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Realizado", x=df_plot[eixo_x], y=df_plot["valor_total"],
        marker_color=CORES[0], marker_line_width=0,
        text=[f"R$ {v:,.0f}" for v in df_plot["valor_total"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Realizado: R$ %{y:,.2f}<extra></extra>",
    ))
    if (df_plot["orcamento"] > 0).any():
        fig.add_trace(go.Bar(
            name="Orçamento", x=df_plot[eixo_x], y=df_plot["orcamento"],
            marker_color="rgba(148,163,184,.5)", marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>Orçamento: R$ %{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        **LAYOUT_BASE,
        title=_titulo("Realizado vs Orçamento"),
        barmode="overlay",
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(128,128,128,.15)"),
        xaxis=dict(tickangle=-30),
    )
    return fig


def grafico_horas_por_projeto(df: pd.DataFrame) -> go.Figure:
    eixo_y  = "nome_projeto" if "nome_projeto" in df.columns else "projeto"
    df_plot = df.sort_values("horas_total", ascending=True).tail(20)
    fig = px.bar(
        df_plot, x="horas_total", y=eixo_y, orientation="h",
        color="horas_total",
        color_continuous_scale=[[0,"rgba(37,99,235,.2)"],[1,"rgba(37,99,235,.9)"]],
        text="horas_total",
        title="<b>Horas por Projeto</b>",
    )
    fig.update_traces(
        texttemplate="%{text:.0f} h", textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:.0f} h<extra></extra>",
    )
    fig.update_layout(**LAYOUT_BASE, coloraxis_showscale=False,
                      xaxis=dict(gridcolor="rgba(128,128,128,.15)"))
    return fig


def grafico_custo_por_hora(df: pd.DataFrame) -> go.Figure:
    eixo_x  = "nome_projeto" if "nome_projeto" in df.columns else "projeto"
    df_plot = df[df["custo_por_hora"] > 0].sort_values("custo_por_hora", ascending=False).head(20)
    fig = px.bar(
        df_plot, x=eixo_x, y="custo_por_hora",
        color="custo_por_hora",
        color_continuous_scale=[[0,"rgba(34,197,94,.6)"],[0.5,"rgba(234,179,8,.6)"],[1,"rgba(220,38,38,.8)"]],
        text=[f"R$ {v:.0f}" for v in df_plot["custo_por_hora"]],
        title="<b>Custo por Hora (R$/h)</b>",
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>R$/h: R$ %{y:.2f}<extra></extra>",
    )
    fig.update_layout(**LAYOUT_BASE, coloraxis_showscale=False,
                      yaxis=dict(tickprefix="R$ ", gridcolor="rgba(128,128,128,.15)"),
                      xaxis=dict(tickangle=-30))
    return fig


def grafico_pizza_conta(df_custos: pd.DataFrame) -> go.Figure:
    if "conta" not in df_custos.columns:
        return go.Figure()
    agg   = df_custos.groupby("conta")["realizado"].sum().reset_index()
    agg   = agg[agg["realizado"] > 0].sort_values("realizado", ascending=False)
    total = agg["realizado"].sum()
    agg["pct"] = agg["realizado"] / total * 100
    principais  = agg[agg["pct"] >= 3].copy()
    outros_val  = agg[agg["pct"] < 3]["realizado"].sum()
    if outros_val > 0:
        principais = pd.concat([principais,
            pd.DataFrame([{"conta":"Outros","realizado":outros_val,"pct":outros_val/total*100}])],
            ignore_index=True)
    fig = px.pie(principais, names="conta", values="realizado",
                 title="<b>Custos por Conta Contábil</b>",
                 color_discrete_sequence=CORES, hole=0.45)
    fig.update_traces(
        textposition="outside", textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
    )
    fig.update_layout(**LAYOUT_BASE)
    return fig


def grafico_evolucao_mensal(df_custos: pd.DataFrame,
                             df_horas: pd.DataFrame,
                             mes_col: str = "mes_ref") -> go.Figure:
    fig     = go.Figure()
    val_col = "realizado" if "realizado" in df_custos.columns else "valor"

    if mes_col in df_custos.columns and val_col in df_custos.columns:
        custo_mes = (df_custos.groupby(mes_col)[val_col].sum()
                     .reset_index().sort_values(mes_col))
        fig.add_trace(go.Scatter(
            x=custo_mes[mes_col], y=custo_mes[val_col],
            name="Realizado (R$)", mode="lines+markers",
            line=dict(color=CORES[0], width=2.5),
            marker=dict(size=7, color=CORES[0]),
            fill="tozeroy", fillcolor="rgba(37,99,235,.1)",
            yaxis="y1",
            hovertemplate="%{x}<br>R$ %{y:,.2f}<extra>Realizado</extra>",
        ))

    if mes_col in df_horas.columns and "hs_nor" in df_horas.columns:
        horas_mes = (df_horas.groupby(mes_col)["hs_nor"].sum()
                     .reset_index().sort_values(mes_col))
        fig.add_trace(go.Scatter(
            x=horas_mes[mes_col], y=horas_mes["hs_nor"],
            name="Horas", mode="lines+markers",
            line=dict(color=CORES[1], width=2, dash="dot"),
            marker=dict(size=6, color=CORES[1]),
            yaxis="y2",
            hovertemplate="%{x}<br>%{y:.0f} h<extra>Horas</extra>",
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=_titulo("Evolução Mensal — Realizado e Horas"),
        yaxis=dict(title="Realizado (R$)", tickprefix="R$ ", tickformat=",.0f",
                   gridcolor="rgba(128,128,128,.15)"),
        yaxis2=dict(title="Horas", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
    )
    return fig


def gauge_orcamento(nome_projeto: str, pct: float) -> go.Figure:
    """
    Gauge de consumo de orçamento.
    nome_projeto: nome legível do projeto (não o código CC).
    """
    max_val = max(120, pct + 10) if pct > 100 else 120

    if pct > 100:   cor_bar = "#dc2626"
    elif pct >= 90: cor_bar = "#f59e0b"
    elif pct >= 70: cor_bar = "#f59e0b"
    else:           cor_bar = "#22c55e"

    steps = [
        {"range": [0,   70],  "color": "rgba(34,197,94,.08)"},
        {"range": [70,  90],  "color": "rgba(234,179,8,.08)"},
        {"range": [90, 100],  "color": "rgba(220,38,38,.08)"},
    ]
    if max_val > 100:
        steps.append({"range": [100, max_val], "color": "rgba(220,38,38,.15)"})

    # Trunca nome longo para não sobrepor o gauge
    titulo_display = nome_projeto if len(nome_projeto) <= 28 else nome_projeto[:26] + "…"
    if pct > 100:
        titulo_display += "<br><span style='color:#f87171;font-size:10px'>⚠️ ESTOURO</span>"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number={
            "suffix": "%",
            "font": {"size": 22, "color": cor_bar},
            "valueformat": ".1f",
        },
        delta={
            "reference": 100,
            "relative": False,
            "valueformat": ".1f",
            "suffix": "pp",
            "increasing": {"color": "#f87171"},
            "decreasing": {"color": "#4ade80"},
        },
        title={"text": titulo_display, "font": {"size": 12}},
        gauge={
            "axis": {
                "range": [0, max_val],
                "tickwidth": 1,
                "tickvals": [0, 25, 50, 75, 100] + ([max_val] if pct > 100 else []),
                "tickfont": {"size": 10},
                "tickcolor": "rgba(128,128,128,.5)",
            },
            "bar":       {"color": cor_bar, "thickness": 0.28},
            "bgcolor":   "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps":     steps,
            "threshold": {
                "line": {"color": "#ef4444", "width": 3},
                "thickness": 0.75,
                "value": 100,
            },
        },
    ))
    fig.update_layout(
        height=210,
        margin=dict(l=16, r=16, t=56, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font_color=None,   # herda do tema Streamlit (dark/light)
    )
    return fig


def grafico_horas_colaborador(df_horas: pd.DataFrame,
                               nome_projeto: str | None = None) -> go.Figure:
    col_nome = next((c for c in ["nome","colaborador"] if c in df_horas.columns), None)
    col_h    = next((c for c in ["hs_nor","horas"]     if c in df_horas.columns), None)
    if not col_nome or not col_h:
        return go.Figure()

    agg = (df_horas.groupby(col_nome)[col_h].sum()
           .reset_index().sort_values(col_h, ascending=True))
    titulo = f"<b>Horas por Colaborador{f' — {nome_projeto}' if nome_projeto else ''}</b>"
    fig = px.bar(
        agg, x=col_h, y=col_nome, orientation="h",
        color=col_h,
        color_continuous_scale=[[0,"rgba(37,99,235,.2)"],[1,"rgba(37,99,235,.9)"]],
        text=col_h,
        title=titulo,
    )
    fig.update_traces(
        texttemplate="%{text:.0f} h", textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:.0f} h<extra></extra>",
    )
    fig.update_layout(**LAYOUT_BASE, coloraxis_showscale=False,
                      xaxis=dict(gridcolor="rgba(128,128,128,.15)"))
    return fig
