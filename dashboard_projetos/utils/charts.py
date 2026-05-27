import plotly.graph_objects as go
import pandas as pd

# ── LAYOUT BASE SEGURO ───────────────────────────────────────────────────────
# Configurações universais transparentes. Deixamos o fundo como 'rgba(0,0,0,0)'
# para que o Streamlit trate o visual nativamente via theme="streamlit".
LAYOUT_BASE = {
    "margin": dict(l=20, r=20, t=45, b=20),
    "plot_bgcolor": "rgba(0,0,0,0)",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "hovermode": "closest",
    "font": dict(family="sans-serif", size=12),
}

def grafico_custo_vs_orcamento(df: pd.DataFrame) -> go.Figure:
    """Gera o gráfico de barras comparando Orçamento vs Realizado por projeto."""
    df_sorted = df.sort_values(by="valor_total", ascending=False)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_sorted["nome_projeto"],
        y=df_sorted["orcamento"],
        name="Orçamento",
        marker_color="#2563eb"
    ))
    fig.add_trace(go.Bar(
        x=df_sorted["nome_projeto"],
        y=df_sorted["valor_total"],
        name="Realizado",
        marker_color="#dc2626"
    ))
    
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Orçamento vs Realizado por Projeto</b>",
        barmode="group",
        xaxis=dict(tickangle=-30, gridcolor="rgba(128,128,128,0.1)"),
        yaxis=dict(gridcolor="rgba(128,128,128,0.15)", tickprefix="R$ "),
    )
    return fig

def grafico_realizado_por_projeto(df: pd.DataFrame) -> go.Figure:
    """Gera gráfico simples de Realizado por projeto (caso não haja orçamento)."""
    df_sorted = df.sort_values(by="valor_total", ascending=False)
    
    fig = go.Figure(go.Bar(
        x=df_sorted["nome_projeto"],
        y=df_sorted["valor_total"],
        marker_color="#dc2626",
        text=[f"R$ {v:,.0f}" for v in df_sorted["valor_total"]],
        textposition="auto"
    ))
    
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Custos Realizados por Projeto</b>",
        xaxis=dict(tickangle=-30, gridcolor="rgba(128,128,128,0.1)"),
        yaxis=dict(gridcolor="rgba(128,128,128,0.15)", tickprefix="R$ "),
    )
    return fig

def grafico_pizza_conta(df_custos: pd.DataFrame) -> go.Figure:
    """Gera gráfico de rosca mostrando a distribuição por Conta Contábil (Top 8)."""
    resumo = df_custos.groupby("conta")["realizado"].sum().reset_index()
    resumo = resumo.sort_values(by="realizado", ascending=False).head(8)
    
    fig = go.Figure(go.Pie(
        labels=resumo["conta"],
        values=resumo["realizado"],
        hole=0.4,
        textinfo="percent+label",
        showlegend=False
    ))
    
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Distribuição por Conta Contábil</b>",
    )
    return fig

def grafico_horas_por_projeto(df: pd.DataFrame) -> go.Figure:
    """Gera gráfico de barras de total de horas alocadas por projeto."""
    df_sorted = df.sort_values(by="horas_total", ascending=False)
    
    fig = go.Figure(go.Bar(
        x=df_sorted["nome_projeto"],
        y=df_sorted["horas_total"],
        marker_color="#16a34a",
        text=[f"{v:,.0f}h" for v in df_sorted["horas_total"]],
        textposition="auto"
    ))
    
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Horas Alocadas por Projeto</b>",
        xaxis=dict(tickangle=-30, gridcolor="rgba(128,128,128,0.1)"),
        yaxis=dict(gridcolor="rgba(128,128,128,0.15)"),
    )
    return fig

def grafico_custo_por_hora(df: pd.DataFrame) -> go.Figure:
    """Gera gráfico de barras com a taxa média horária (Custo/Hora)."""
    df_sorted = df.sort_values(by="custo_por_hora", ascending=False)
    
    fig = go.Figure(go.Bar(
        x=df_sorted["nome_projeto"],
        y=df_sorted["custo_por_hora"],
        marker_color="#eab308",
        text=[f"R$ {v:.2f}/h" for v in df_sorted["custo_por_hora"]],
        textposition="auto"
    ))
    
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Custo Médio por Hora</b>",
        xaxis=dict(tickangle=-30, gridcolor="rgba(128,128,128,0.1)"),
        yaxis=dict(gridcolor="rgba(128,128,128,0.15)", tickprefix="R$ "),
    )
    return fig

def grafico_evolucao_mensal(df_custos: pd.DataFrame, df_horas: pd.DataFrame, mes_col: str) -> go.Figure:
    """Gera gráfico de linha temporal demonstrando a evolução de desembolsos mensais."""
    custo_mes = df_custos.groupby(mes_col)["realizado"].sum().reset_index()
    custo_mes = custo_mes.sort_values(by=mes_col)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=custo_mes[mes_col],
        y=custo_mes["realizado"],
        mode="lines+markers",
        name="Custo Mensal",
        line=dict(color="#2563eb", width=3),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Evolução Mensal de Custos</b>",
        xaxis=dict(gridcolor="rgba(128,128,128,0.1)"),
        yaxis=dict(gridcolor="rgba(128,128,128,0.15)", tickprefix="R$ "),
    )
    return fig

def gauge_orcamento(titulo: str, pct: float) -> go.Figure:
    """Gera o micro-gráfico de ponteiro (Gauge) de consumo orçamentário."""
    cor_barra = "#dc2626" if pct > 100 else ("#eab308" if pct >= 80 else "#16a34a")
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        title={'text': titulo, 'font': {'size': 13}},
        number={'suffix': "%", 'font': {'size': 16}},
        gauge={
            'axis': {'range': [0, max(100, pct)], 'tickwidth': 1},
            'bar': {'color': cor_barra},
            'bgcolor': "rgba(128,128,128,0.05)",
            'borderwidth': 1,
            'bordercolor': "rgba(128,128,128,0.15)"
        }
    ))
    
    fig.update_layout(
        margin=dict(l=15, r=15, t=35, b=10),
        height=135,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig

def grafico_horas_colaborador(df_h_proj: pd.DataFrame, nome_projeto: str) -> go.Figure:
    """Gera o gráfico de barras horizontais detalhando as horas de cada colaborador."""
    resumo = df_h_proj.groupby("nome")["hs_nor"].sum().reset_index()
    resumo = resumo.sort_values(by="hs_nor", ascending=True)
    
    fig = go.Figure(go.Bar(
        y=resumo["nome"],
        x=resumo["hs_nor"],
        orientation='h',
        marker_color="#2563eb",
        text=[f"{v:,.0f}h" for v in resumo["hs_nor"]],
        textposition="inside"
    ))
    
    fig.update_layout(
        **LAYOUT_BASE,
        title=f"<b>Horas por Colaborador — {nome_projeto}</b>",
        xaxis=dict(gridcolor="rgba(128,128,128,0.1)"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
    )
    return fig
