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
    hoverlabel=dict(bgcolor="white", font_size=12, bordercolor="#e2e8f0"),
)


def _titulo(texto: str) -> dict:
    return dict(text=f"<b>{texto}</b>", font=dict(size=14, color="#1e293b"))


def grafico_realizado_por_projeto(df: pd.DataFrame) -> go.Figure:
    df_plot = df.sort_values("valor_total", ascending=False).head(20)
    fig = go.Figure(go.Bar(
        x=df_plot["projeto"],
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
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="#f1f5f9"),
        xaxis=dict(tickangle=-30),
    )
    return fig


def grafico_custo_vs_orcamento(df: pd.DataFrame) -> go.Figure:
    df_plot = df.sort_values("valor_total", ascending=False).head(20)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Realizado", x=df_plot["projeto"], y=df_plot["valor_total"],
        marker_color=CORES[0], marker_line_width=0,
        text=[f"R$ {v:,.0f}" for v in df_plot["valor_total"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Realizado: R$ %{y:,.2f}<extra></extra>",
    ))
    if (df_plot["orcamento"] > 0).any():
        fig.add_trace(go.Bar(
            name="Orçamento", x=df_plot["projeto"], y=df_plot["orcamento"],
            marker_color="#94a3b8", marker_line_width=0, opacity=0.55,
            hovertemplate="<b>%{x}</b><br>Orçamento: R$ %{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        **LAYOUT_BASE,
        title=_titulo("Realizado vs Orçamento"),
        barmode="overlay",
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="#f1f5f9"),
        xaxis=dict(tickangle=-30),
    )
    return fig


def grafico_horas_por_projeto(df: pd.DataFrame) -> go.Figure:
    df_plot = df.sort_values("horas_total", ascending=True).tail(20)
    fig = px.bar(
        df_plot, x="horas_total", y="projeto", orientation="h",
        color="horas_total",
        color_continuous_scale=[[0,"#dbeafe"],[1,"#1d4ed8"]],
        text="horas_total",
        title="<b>Horas por Projeto</b>",
    )
    fig.update_traces(
        texttemplate="%{text:.0f} h", textposition="outside",
        hovertemplate="<b>%{y}</b><br>Horas: %{x:.0f} h<extra></extra>",
    )
    fig.update_layout(**LAYOUT_BASE, coloraxis_showscale=False,
                      xaxis=dict(gridcolor="#f1f5f9"))
    return fig


def grafico_custo_por_hora(df: pd.DataFrame) -> go.Figure:
    df_plot = df[df["custo_por_hora"] > 0].sort_values("custo_por_hora", ascending=False).head(20)
    fig = px.bar(
        df_plot, x="projeto", y="custo_por_hora",
        color="custo_por_hora",
        color_continuous_scale=[[0,"#dcfce7"],[0.5,"#fef9c3"],[1,"#fee2e2"]],
        text=[f"R$ {v:.0f}" for v in df_plot["custo_por_hora"]],
        title="<b>Custo por Hora (R$/h)</b>",
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>R$/h: R$ %{y:.2f}<extra></extra>",
    )
    fig.update_layout(**LAYOUT_BASE, coloraxis_showscale=False,
                      yaxis=dict(tickprefix="R$ ", gridcolor="#f1f5f9"),
                      xaxis=dict(tickangle=-30))
    return fig


def grafico_pizza_conta(df_custos: pd.DataFrame) -> go.Figure:
    if "conta" not in df_custos.columns:
        return go.Figure()
    agg = df_custos.groupby("conta")["realizado"].sum().reset_index()
    agg = agg[agg["realizado"] > 0].sort_values("realizado", ascending=False)
    # Agrupa contas pequenas em "Outros" para não poluir
    total = agg["realizado"].sum()
    agg["pct"] = agg["realizado"] / total * 100
    principais = agg[agg["pct"] >= 3].copy()
    outros_val = agg[agg["pct"] < 3]["realizado"].sum()
    if outros_val > 0:
        outros_row = pd.DataFrame([{"conta": "Outros", "realizado": outros_val, "pct": outros_val/total*100}])
        principais = pd.concat([principais, outros_row], ignore_index=True)

    fig = px.pie(
        principais, names="conta", values="realizado",
        title="<b>Custos por Conta Contábil</b>",
        color_discrete_sequence=CORES,
        hole=0.45,
    )
    fig.update_traces(
        textposition="outside", textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
    )
    fig.update_layout(**LAYOUT_BASE)
    return fig


def grafico_pizza_categorias(df_custos: pd.DataFrame) -> go.Figure:
    col = "categoria" if "categoria" in df_custos.columns else (
          "conta"     if "conta"     in df_custos.columns else None)
    val = "realizado" if "realizado" in df_custos.columns else "valor"
    if not col or val not in df_custos.columns:
        return go.Figure()
    agg = df_custos.groupby(col)[val].sum().reset_index()
    fig = px.pie(agg, names=col, values=val,
                 title="<b>Distribuição de Custos</b>",
                 color_discrete_sequence=CORES, hole=0.45)
    fig.update_traces(textposition="outside", textinfo="percent+label")
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
            line=dict(color=CORES[0], width=2.5),
            marker=dict(size=7, color=CORES[0]),
            fill="tozeroy", fillcolor="rgba(37,99,235,0.08)",
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
                   gridcolor="#f1f5f9"),
        yaxis2=dict(title="Horas", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
    )
    return fig


def gauge_orcamento(projeto: str, pct: float) -> go.Figure:
    max_val = max(120, pct + 10) if pct > 100 else 120

    if pct > 100:   cor_bar = "#dc2626"
    elif pct >= 90: cor_bar = "#f59e0b"
    elif pct >= 70: cor_bar = "#f59e0b"
    else:           cor_bar = "#16a34a"

    steps = [
        {"range": [0, 70],  "color": "#f0fdf4"},
        {"range": [70, 90], "color": "#fefce8"},
        {"range": [90, 100],"color": "#fff1f2"},
    ]
    if max_val > 100:
        steps.append({"range": [100, max_val], "color": "#fee2e2"})

    titulo = projeto
    if pct > 100:
        titulo += "<br><span style='color:#dc2626;font-size:11px'>⚠️ ESTOURO</span>"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number={"suffix": "%", "font": {"size": 20, "color": cor_bar}, "valueformat": ".1f"},
        delta={"reference": 100, "relative": False, "valueformat": ".1f",
               "suffix": "pp",
               "increasing": {"color": "#dc2626"},
               "decreasing": {"color": "#16a34a"}},
        title={"text": titulo, "font": {"size": 11, "color": "#475569"}},
        gauge={
            "axis": {"range": [0, max_val], "tickwidth": 1, "tickcolor": "#94a3b8",
                     "tickvals": [0, 25, 50, 75, 100] + ([max_val] if pct > 100 else [])},
            "bar":  {"color": cor_bar, "thickness": 0.25},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": steps,
            "threshold": {"line": {"color": "#dc2626", "width": 3},
                          "thickness": 0.75, "value": 100},
        },
    ))
    fig.update_layout(
        height=200,
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
    fig = px.bar(
        agg, x=col_h, y=col_nome, orientation="h",
        color=col_h,
        color_continuous_scale=[[0,"#dbeafe"],[1,"#1d4ed8"]],
        text=col_h,
        title=f"<b>Horas por Colaborador{f' — {projeto}' if projeto else ''}</b>",
    )
    fig.update_traces(
        texttemplate="%{text:.0f} h", textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:.0f} h<extra></extra>",
    )
    fig.update_layout(**LAYOUT_BASE, coloraxis_showscale=False,
                      xaxis=dict(gridcolor="#f1f5f9"))
    return fig
