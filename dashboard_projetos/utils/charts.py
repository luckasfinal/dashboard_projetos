import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, date

CORES = px.colors.qualitative.Set2

# Máximo de projetos exibidos nos gráficos de barras (evita poluição visual).
# Usado tanto no corte quanto no aviso de truncamento (Roadmap 1.2).
LIMITE_GRAFICO = 20

# LAYOUT_BASE sem margin e legend — cada função define os seus própria
# para evitar conflito de kwargs duplicados no update_layout
LAYOUT_BASE = dict(
    font_family="Inter, sans-serif",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
)

_LEGEND_H = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
_MARGIN   = dict(l=20, r=20, t=44, b=20)


def grafico_realizado_por_projeto(df: pd.DataFrame) -> go.Figure:
    eixo = "nome_projeto" if "nome_projeto" in df.columns else "projeto"
    df_plot = df.sort_values("valor_total", ascending=False).head(LIMITE_GRAFICO)
    fig = go.Figure(go.Bar(
        x=df_plot[eixo], y=df_plot["valor_total"],
        marker_color="#4C78A8", marker_line_width=0,
        text=[f"R$ {v:,.0f}" for v in df_plot["valor_total"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Realizado: R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Realizado por Projeto</b>",
        legend=_LEGEND_H, margin=_MARGIN,
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(128,128,128,.15)"),
        xaxis=dict(tickangle=-30),
    )
    return fig


def grafico_custo_vs_orcamento(df: pd.DataFrame) -> go.Figure:
    eixo = "nome_projeto" if "nome_projeto" in df.columns else "projeto"
    fig = go.Figure()

    # Destaque de estouro: barras "Realizado" ficam vermelhas quando
    # valor_total > orcamento (e há orçamento cadastrado para o projeto)
    cores_realizado = []
    for _, r in df.iterrows():
        orc = r.get("orcamento", 0) or 0
        val = r.get("valor_total", 0) or 0
        if orc > 0 and val > orc:
            cores_realizado.append("#dc2626")   # vermelho — estouro
        else:
            cores_realizado.append("#4C78A8")   # azul padrão

    textos_realizado = []
    for _, r in df.iterrows():
        orc = r.get("orcamento", 0) or 0
        val = r.get("valor_total", 0) or 0
        txt = f"R$ {val:,.0f}"
        if orc > 0 and val > orc:
            txt += " 🚨"
        textos_realizado.append(txt)

    fig.add_trace(go.Bar(
        name="Realizado", x=df[eixo], y=df["valor_total"],
        marker_color=cores_realizado, marker_line_width=0,
        text=textos_realizado,
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Realizado: R$ %{y:,.2f}<extra></extra>",
    ))
    if (df["orcamento"] > 0).any():
        fig.add_trace(go.Bar(
            name="Orçamento", x=df[eixo], y=df["orcamento"],
            marker_color="rgba(148,163,184,.5)", marker_line_width=0,
            hovertemplate="<b>%{x}</b><br>Orçamento: R$ %{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Realizado vs Orçamento</b> <span style='font-size:11px;opacity:.6'>(🚨 = estouro de orçamento)</span>",
        legend=_LEGEND_H, margin=_MARGIN,
        barmode="overlay",
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(128,128,128,.15)"),
        xaxis=dict(tickangle=-30),
    )
    return fig


def grafico_horas_por_projeto(df: pd.DataFrame) -> go.Figure:
    eixo = "nome_projeto" if "nome_projeto" in df.columns else "projeto"
    df_plot = df.sort_values("horas_total", ascending=True).tail(LIMITE_GRAFICO)
    fig = px.bar(
        df_plot, x="horas_total", y=eixo, orientation="h",
        color="horas_total",
        color_continuous_scale=[[0, "rgba(37,99,235,.2)"], [1, "rgba(37,99,235,.9)"]],
        text="horas_total",
        title="<b>Horas por Projeto</b>",
    )
    fig.update_traces(
        texttemplate="%{text:.0f} h", textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:.0f} h<extra></extra>",
    )
    fig.update_layout(
        **LAYOUT_BASE,
        legend=_LEGEND_H, margin=_MARGIN,
        coloraxis_showscale=False,
        xaxis=dict(gridcolor="rgba(128,128,128,.15)"),
    )
    return fig


def grafico_custo_por_hora(df: pd.DataFrame) -> go.Figure:
    eixo = "nome_projeto" if "nome_projeto" in df.columns else "projeto"
    df_plot = df[df["custo_por_hora"] > 0].sort_values("custo_por_hora", ascending=False).head(LIMITE_GRAFICO)
    fig = px.bar(
        df_plot, x=eixo, y="custo_por_hora",
        color="custo_por_hora",
        color_continuous_scale=[[0,"rgba(34,197,94,.6)"],[0.5,"rgba(234,179,8,.6)"],[1,"rgba(220,38,38,.8)"]],
        text=[f"R$ {v:.0f}" for v in df_plot["custo_por_hora"]],
        title="<b>Custo por Hora (R$/h)</b>",
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>R$/h: R$ %{y:.2f}<extra></extra>",
    )
    fig.update_layout(
        **LAYOUT_BASE,
        legend=_LEGEND_H, margin=_MARGIN,
        coloraxis_showscale=False,
        yaxis=dict(tickprefix="R$ ", gridcolor="rgba(128,128,128,.15)"),
        xaxis=dict(tickangle=-30),
    )
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
        principais = pd.concat([
            principais,
            pd.DataFrame([{"conta": "Outros", "realizado": outros_val, "pct": outros_val/total*100}])
        ], ignore_index=True)
    fig = px.pie(
        principais, names="conta", values="realizado",
        title="<b>Custos por Conta Contábil</b>",
        color_discrete_sequence=CORES, hole=0.45,
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent",
        insidetextorientation="radial",
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
    )
    fig.update_layout(
        **LAYOUT_BASE,
        # legenda vertical à direita — não sobrepõe as fatias
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, font=dict(size=11)),
        margin=dict(l=20, r=160, t=44, b=20),
        height=380,
    )
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
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(**LAYOUT_BASE, legend=_LEGEND_H, margin=_MARGIN)
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
            line=dict(color="#4C78A8", width=2.5),
            marker=dict(size=7),
            fill="tozeroy", fillcolor="rgba(76,120,168,.1)",
            yaxis="y1",
            hovertemplate="%{x}<br>R$ %{y:,.2f}<extra>Realizado</extra>",
        ))

    if mes_col in df_horas.columns and "hs_nor" in df_horas.columns:
        horas_mes = (df_horas.groupby(mes_col)["hs_nor"].sum()
                     .reset_index().sort_values(mes_col))
        fig.add_trace(go.Scatter(
            x=horas_mes[mes_col], y=horas_mes["hs_nor"],
            name="Horas", mode="lines+markers",
            line=dict(color="#F58518", width=2, dash="dot"),
            marker=dict(size=6),
            yaxis="y2",
            hovertemplate="%{x}<br>%{y:.0f} h<extra>Horas</extra>",
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Evolução Mensal — Realizado e Horas</b>",
        legend=_LEGEND_H, margin=_MARGIN,
        yaxis=dict(title="Realizado (R$)", tickprefix="R$ ", tickformat=",.0f",
                   gridcolor="rgba(128,128,128,.15)"),
        yaxis2=dict(title="Horas", overlaying="y", side="right", showgrid=False),
        hovermode="x unified",
    )
    return fig


def gauge_orcamento(nome_projeto: str, pct: float) -> go.Figure:
    max_val = max(120, pct + 10) if pct > 100 else 120
    cor_bar = ("#dc2626" if pct > 100 else
               "#f59e0b" if pct >= 90 else
               "#f59e0b" if pct >= 70 else "#22c55e")
    steps = [
        {"range": [0,   70],  "color": "rgba(34,197,94,.08)"},
        {"range": [70,  90],  "color": "rgba(234,179,8,.08)"},
        {"range": [90, 100],  "color": "rgba(220,38,38,.08)"},
    ]
    if max_val > 100:
        steps.append({"range": [100, max_val], "color": "rgba(220,38,38,.15)"})

    titulo = (nome_projeto[:26] + "…") if len(nome_projeto) > 28 else nome_projeto
    if pct > 100:
        titulo += "<br><span style='color:#f87171;font-size:10px'>⚠️ ESTOURO</span>"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=pct,
        number={"suffix": "%", "font": {"size": 22, "color": cor_bar}, "valueformat": ".1f"},
        delta={"reference": 100, "relative": False, "valueformat": ".1f", "suffix": "pp",
               "increasing": {"color": "#f87171"}, "decreasing": {"color": "#4ade80"}},
        title={"text": titulo, "font": {"size": 12}},
        gauge={
            "axis": {"range": [0, max_val], "tickwidth": 1,
                     "tickvals": [0, 25, 50, 75, 100] + ([max_val] if pct > 100 else []),
                     "tickfont": {"size": 10}, "tickcolor": "rgba(128,128,128,.5)"},
            "bar":       {"color": cor_bar, "thickness": 0.28},
            "bgcolor":   "rgba(0,0,0,0)",
            "borderwidth": 0,
            "steps":     steps,
            "threshold": {"line": {"color": "#ef4444", "width": 3}, "thickness": 0.75, "value": 100},
        },
    ))
    fig.update_layout(
        height=210,
        margin=dict(l=16, r=16, t=56, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def grafico_horas_colaborador(df_horas: pd.DataFrame,
                               nome_projeto: str | None = None) -> go.Figure:
    df = df_horas.copy()
    col_nome = next((c for c in ["nome", "colaborador"] if c in df.columns), None)
    col_h    = next((c for c in ["hs_nor", "horas"]     if c in df.columns), None)
    if not col_nome or not col_h:
        return go.Figure()

    col_area = next((c for c in ["descricao_cc_origem", "cc_origem", "area"]
                     if c in df.columns), None)
    if col_area:
        df["_label"] = df[col_nome].astype(str) + " — " + df[col_area].astype(str)
    else:
        df["_label"] = df[col_nome].astype(str)

    agg = (df.groupby("_label")[col_h].sum()
             .reset_index()
             .sort_values(col_h, ascending=True))

    titulo = f"<b>Distribuição de Horas por Colaborador"
    if nome_projeto:
        titulo += f" — {nome_projeto}"
    titulo += "</b>"

    fig = px.bar(
        agg, x=col_h, y="_label", orientation="h",
        color=col_h,
        color_continuous_scale=[[0, "rgba(76,120,168,.25)"], [1, "rgba(76,120,168,.9)"]],
        text=col_h, title=titulo,
    )
    fig.update_traces(
        texttemplate="%{text:.0f} h", textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:.0f} h<extra></extra>",
    )
    fig.update_layout(
        **LAYOUT_BASE,
        legend=_LEGEND_H, margin=_MARGIN,
        coloraxis_showscale=False,
        xaxis=dict(gridcolor="rgba(128,128,128,.15)"),
        yaxis_title=None,
    )
    return fig


def grafico_evolucao_mensal_projeto(df_custos_proj: pd.DataFrame,
                                    nome_projeto: str | None = None) -> go.Figure:
    if df_custos_proj.empty:
        return go.Figure()

    mes_col = "mes_ref" if "mes_ref" in df_custos_proj.columns else None
    val_col = "realizado" if "realizado" in df_custos_proj.columns else "valor"
    if not mes_col or val_col not in df_custos_proj.columns:
        return go.Figure()

    custo_mes = (df_custos_proj.groupby(mes_col)[val_col].sum()
                 .reset_index().sort_values(mes_col))
    custo_mes["acumulado"] = custo_mes[val_col].cumsum()

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=custo_mes[mes_col], y=custo_mes["acumulado"],
        name="Acumulado",
        mode="lines",
        line=dict(color="rgba(76,120,168,.5)", width=2),
        fill="tozeroy", fillcolor="rgba(76,120,168,.10)",
        yaxis="y2",
        hovertemplate="%{x}<br>Acumulado: R$ %{y:,.2f}<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=custo_mes[mes_col], y=custo_mes[val_col],
        name="Mensal",
        marker_color="rgba(76,120,168,.8)", marker_line_width=0,
        yaxis="y1",
        text=[f"R$ {v:,.0f}" for v in custo_mes[val_col]],
        textposition="outside",
        hovertemplate="%{x}<br>Mensal: R$ %{y:,.2f}<extra></extra>",
    ))

    titulo = "<b>Evolução Mensal de Desembolsos"
    if nome_projeto:
        titulo += f" — {nome_projeto}"
    titulo += "</b>"

    fig.update_layout(
        **LAYOUT_BASE,
        title=titulo,
        legend=_LEGEND_H, margin=_MARGIN,
        yaxis=dict(title="Desembolso Mensal (R$)", tickprefix="R$ ", tickformat=",.0f",
                   gridcolor="rgba(128,128,128,.15)"),
        yaxis2=dict(title="Acumulado (R$)", tickprefix="R$ ", tickformat=",.0f",
                    overlaying="y", side="right", showgrid=False),
        hovermode="x unified",
        showlegend=True,
    )
    return fig


def grafico_timeline_lancamentos(df: pd.DataFrame) -> go.Figure:
    """
    Timeline (Gantt enxuto) dos lançamentos do portfólio — Roadmap 3.1.

    Para cada projeto com data de lançamento (prevista e/ou realizada),
    desenha marcadores na linha do tempo:
      - losango cinza  = lançamento previsto
      - estrela verde  = lançamento realizado
    Um traço pontilhado liga previsto→realizado quando ambos existem.
    Linha vertical vermelha marca a data de HOJE.

    Cada projeto ocupa uma linha (eixo Y). Ordena pelo previsto mais próximo.
    """

    def _parse(val):
        if not val or str(val) in ("0", "None", "nan", ""):
            return None
        try:
            return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    eixo_nome = "nome_projeto" if "nome_projeto" in df.columns else "projeto"

    linhas = []
    for _, row in df.iterrows():
        prev_d = _parse(row.get("prev_lancamento"))
        real_d = _parse(row.get("real_lancamento"))
        if prev_d is None and real_d is None:
            continue
        linhas.append({
            "nome": str(row.get(eixo_nome, row.get("projeto", "—"))),
            "prev": prev_d,
            "real": real_d,
            "ord": prev_d or real_d,
        })

    if not linhas:
        return go.Figure()

    # Ordena: lançamentos mais próximos no topo (eixo Y invertido depois)
    linhas.sort(key=lambda x: x["ord"], reverse=True)
    nomes = [l["nome"] for l in linhas]

    hoje = date.today()
    fig = go.Figure()

    # Traço ligando previsto → realizado
    for l in linhas:
        if l["prev"] and l["real"]:
            atrasado = l["real"] > l["prev"]
            cor_linha = "rgba(220,38,38,.5)" if atrasado else "rgba(34,197,94,.5)"
            fig.add_trace(go.Scatter(
                x=[l["prev"], l["real"]], y=[l["nome"], l["nome"]],
                mode="lines",
                line=dict(color=cor_linha, width=2, dash="dot"),
                showlegend=False, hoverinfo="skip",
            ))

    # Marcadores previstos
    prev_x = [l["prev"] for l in linhas if l["prev"]]
    prev_y = [l["nome"] for l in linhas if l["prev"]]
    if prev_x:
        fig.add_trace(go.Scatter(
            x=prev_x, y=prev_y, mode="markers", name="Previsto",
            marker=dict(symbol="diamond", size=12, color="#94a3b8",
                        line=dict(width=1, color="#64748b")),
            hovertemplate="<b>%{y}</b><br>Previsto: %{x|%d/%m/%Y}<extra></extra>",
        ))

    # Marcadores realizados
    real_x = [l["real"] for l in linhas if l["real"]]
    real_y = [l["nome"] for l in linhas if l["real"]]
    if real_x:
        fig.add_trace(go.Scatter(
            x=real_x, y=real_y, mode="markers", name="Realizado",
            marker=dict(symbol="star", size=14, color="#22c55e",
                        line=dict(width=1, color="#16a34a")),
            hovertemplate="<b>%{y}</b><br>Realizado: %{x|%d/%m/%Y}<extra></extra>",
        ))

    # Linha vertical do "hoje"
    fig.add_vline(
        x=hoje, line_width=2, line_dash="solid", line_color="rgba(220,38,38,.7)",
    )
    fig.add_annotation(
        x=hoje, y=1.02, yref="paper", showarrow=False,
        text="hoje", font=dict(size=11, color="#dc2626"),
    )

    altura = max(260, 42 * len(nomes) + 90)
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Timeline de Lançamentos do Portfólio</b>",
        legend=_LEGEND_H,
        margin=dict(l=20, r=20, t=60, b=20),
        height=altura,
        xaxis=dict(title=None, gridcolor="rgba(128,128,128,.15)", type="date"),
        yaxis=dict(title=None, categoryorder="array", categoryarray=nomes,
                   gridcolor="rgba(128,128,128,.08)"),
        hovermode="closest",
    )
    return fig


# ─────────────────────────────────────────────
# Dashboard Executivo — gráficos
# ─────────────────────────────────────────────

CORES_CATEGORIA: dict[str, str] = {
    "Mão de obra": "#4C78A8",
    "Terceiros":   "#F58518",
    "Materiais":   "#54A24B",
    "Viagens":     "#B279A2",
    "Outras":      "#9D755D",
}

_COR_QUADRANTE: dict[str, str] = {
    "Controlado":     "#22c55e",
    "Risco de Prazo": "#f59e0b",
    "Risco de Custo": "#f97316",
    "Crítico":        "#ef4444",
}


def grafico_evolucao_fisica(df_status: pd.DataFrame) -> go.Figure:
    """Barras horizontais de % concluído por projeto."""
    df_plot = df_status.sort_values("pct_concluido", ascending=True).tail(LIMITE_GRAFICO)
    fig = go.Figure(go.Bar(
        y=df_plot["nome_projeto"],
        x=(df_plot["pct_concluido"] * 100).round(1),
        orientation="h",
        marker_color="#4C78A8",
        text=[f"{v*100:.0f}%" for v in df_plot["pct_concluido"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Concluído: %{x:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Evolução Física dos Projetos</b>",
        margin=_MARGIN,
        xaxis=dict(range=[0, 115], ticksuffix="%", gridcolor="rgba(128,128,128,.15)"),
    )
    return fig


def grafico_custos_empilhados(df_cat: pd.DataFrame) -> go.Figure:
    """Barras empilhadas custo por projeto e conta contábil (top 8 contas)."""
    cat_col = "conta" if "conta" in df_cat.columns else "categoria_custo"
    eixo    = "nome_projeto" if "nome_projeto" in df_cat.columns else "projeto"
    nomes   = df_cat[eixo].unique()[:LIMITE_GRAFICO]
    top_cats = (
        df_cat.groupby(cat_col)["total_custo"].sum()
        .nlargest(8).index.tolist()
    )
    fig = go.Figure()
    for i, cat in enumerate(top_cats):
        df_c   = df_cat[df_cat[cat_col] == cat]
        valores = [float(df_c[df_c[eixo] == p]["total_custo"].sum()) for p in nomes]
        if any(v > 0 for v in valores):
            label = str(cat)[:35]
            fig.add_trace(go.Bar(
                name=label, x=list(nomes), y=valores,
                marker_color=CORES[i % len(CORES)],
                hovertemplate=f"<b>%{{x}}</b><br>{label}: R$ %{{y:,.0f}}<extra></extra>",
            ))
    outros = df_cat[~df_cat[cat_col].isin(top_cats)]
    if not outros.empty:
        outros_vals = [float(outros[outros[eixo] == p]["total_custo"].sum()) for p in nomes]
        if any(v > 0 for v in outros_vals):
            fig.add_trace(go.Bar(
                name="Outros", x=list(nomes), y=outros_vals,
                marker_color="#94a3b8",
                hovertemplate="<b>%{x}</b><br>Outros: R$ %{y:,.0f}<extra></extra>",
            ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Custos por Projeto e Conta Contábil</b>",
        barmode="stack", legend=_LEGEND_H, margin=_MARGIN,
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(128,128,128,.15)"),
        xaxis=dict(tickangle=-30),
    )
    return fig


def grafico_distribuicao_custos(df_cat: pd.DataFrame) -> go.Figure:
    """Donut de custos por conta contábil (agrupa <3% em Outros)."""
    cat_col    = "conta" if "conta" in df_cat.columns else "categoria_custo"
    total      = df_cat.groupby(cat_col)["total_custo"].sum().reset_index()
    grand_total = total["total_custo"].sum()
    if grand_total > 0:
        total["pct"] = total["total_custo"] / grand_total * 100
        principais   = total[total["pct"] >= 3].copy()
        outros_val   = total[total["pct"] < 3]["total_custo"].sum()
        if outros_val > 0:
            principais = pd.concat([
                principais,
                pd.DataFrame([{cat_col: "Outros", "total_custo": outros_val}]),
            ], ignore_index=True)
        total = principais
    fig = go.Figure(go.Pie(
        labels=total[cat_col],
        values=total["total_custo"],
        hole=0.45,
        marker_colors=[CORES[i % len(CORES)] for i in range(len(total))],
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.0f} · %{percent}<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Distribuição por Conta Contábil</b>",
        margin=dict(l=20, r=160, t=44, b=20),
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02, font=dict(size=11)),
    )
    return fig


def grafico_burn_rate_temporal(df_br: pd.DataFrame) -> go.Figure:
    """Linha de custo acumulado mensal (top 10 projetos)."""
    label_col = "nome_projeto" if "nome_projeto" in df_br.columns else "projeto"
    top_projs = (
        df_br.groupby("projeto")["custo_acumulado"].max()
        .nlargest(10).index.tolist()
    )
    fig = go.Figure()
    for i, proj in enumerate(top_projs):
        df_p  = df_br[df_br["projeto"] == proj].sort_values("mes_ref")
        label = str(df_p[label_col].iloc[0])[:35] if not df_p.empty else proj[:20]
        fig.add_trace(go.Scatter(
            x=df_p["mes_ref"], y=df_p["custo_acumulado"],
            mode="lines+markers", name=label,
            line=dict(color=CORES[i % len(CORES)]),
            hovertemplate=f"<b>{label}</b><br>%{{x}}<br>Acumulado: R$ %{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Burn Rate — Custo Acumulado por Projeto</b>",
        legend=_LEGEND_H, margin=_MARGIN,
        yaxis=dict(tickprefix="R$ ", tickformat=",.0f", gridcolor="rgba(128,128,128,.15)"),
        xaxis=dict(gridcolor="rgba(128,128,128,.15)"),
    )
    return fig


def grafico_matriz_executiva(df_matriz: pd.DataFrame) -> go.Figure:
    """Scatter de 4 quadrantes Prazo × Custo."""
    fig = go.Figure()
    for quadrante, grp in df_matriz.groupby("quadrante"):
        fig.add_trace(go.Scatter(
            x=grp["desvio_prazo_dias"], y=grp["desvio_eac_pct"],
            mode="markers+text", name=quadrante,
            marker=dict(size=14, color=_COR_QUADRANTE.get(quadrante, "#94a3b8"),
                        opacity=0.85, line=dict(width=1, color="rgba(255,255,255,0.2)")),
            text=grp["nome_projeto"].apply(lambda n: (str(n)[:12] + "…") if len(str(n)) > 12 else str(n)),
            textposition="top center",
            textfont=dict(size=9, color="rgba(255,255,255,0.85)"),
            hovertemplate="<b>%{text}</b><br>Desvio prazo: %{x} dias<br>Desvio custo: %{y:.1f}%<extra></extra>",
        ))
    fig.add_vline(x=0, line_dash="dash", line_color="rgba(148,163,184,.4)")
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(148,163,184,.4)")
    for texto, xr, yr, xa, ya in [
        ("🟢 Controlado",  0.02, 0.02, "left",  "bottom"),
        ("🟡 Risco Prazo", 0.98, 0.02, "right", "bottom"),
        ("🟠 Risco Custo", 0.02, 0.98, "left",  "top"),
        ("🔴 Crítico",     0.98, 0.98, "right", "top"),
    ]:
        fig.add_annotation(xref="paper", yref="paper", x=xr, y=yr, text=texto,
                           showarrow=False, font=dict(size=10, color="rgba(148,163,184,.55)"),
                           xanchor=xa, yanchor=ya)
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Matriz Executiva — Prazo × Custo</b>",
        legend=_LEGEND_H, margin=_MARGIN,
        xaxis_title="Desvio de Prazo (dias)",
        yaxis_title="Desvio de Custo EAC (%)",
        xaxis=dict(zeroline=False, gridcolor="rgba(128,128,128,.15)"),
        yaxis=dict(zeroline=False, gridcolor="rgba(128,128,128,.15)"),
        hovermode="closest",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Gantt do Portfólio (A5)
# ─────────────────────────────────────────────────────────────────────────────

def grafico_gantt_portfolio(df_f: pd.DataFrame) -> "go.Figure | None":
    """Gantt horizontal: uma barra por projeto de data_inicio a prev/real_lancamento."""
    import plotly.express as px

    def _pd(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        try:
            return pd.Timestamp(str(v))
        except Exception:
            return None

    linhas = []
    for _, row in df_f.iterrows():
        ini = _pd(row.get("data_inicio"))
        fim = _pd(row.get("real_lancamento")) or _pd(row.get("prev_lancamento"))
        if ini is None or fim is None:
            continue
        if fim < ini:
            fim = ini + pd.Timedelta(days=1)
        nome   = str(row.get("nome_projeto") or row.get("projeto") or "")[:40]
        status = str(row.get("status_projeto") or "—").strip()
        linhas.append({"Projeto": nome, "Início": ini, "Fim": fim, "Status": status})

    if not linhas:
        return None

    df_g = pd.DataFrame(linhas).sort_values("Início")

    _cores = {
        "CC criado": "#4C78A8", "Viabilizado": "#54A24B",
        "Em desenvolvimento": "#E45756", "Em lançamento": "#F58518",
        "Lançado": "#72B7B2", "Stand by": "#B279A2",
        "Cancelado": "#BAB0AC", "—": "#9ecae1",
    }

    fig = px.timeline(
        df_g, x_start="Início", x_end="Fim", y="Projeto",
        color="Status", color_discrete_map=_cores,
        title="<b>Gantt do Portfólio</b>",
    )
    fig.update_yaxes(autorange="reversed")
    fig.add_vline(
        x=str(date.today()), line_dash="dot",
        line_color="rgba(255,200,0,.7)",
        annotation_text="Hoje", annotation_position="top right",
        annotation_font_size=10,
    )
    fig.update_layout(
        **LAYOUT_BASE, margin=_MARGIN, legend=_LEGEND_H,
        height=max(320, len(df_g) * 28 + 80),
        xaxis_title="",
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Top Colaboradores por Horas (B1)
# ─────────────────────────────────────────────────────────────────────────────

def grafico_top_colaboradores(df_horas: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Bar chart horizontal dos top N colaboradores por horas normais."""
    if df_horas.empty or "nome" not in df_horas.columns or "hs_nor" not in df_horas.columns:
        return go.Figure()
    df_top = (
        df_horas.groupby("nome")["hs_nor"].sum()
        .nlargest(top_n).reset_index()
        .sort_values("hs_nor")
    )
    fig = go.Figure(go.Bar(
        x=df_top["hs_nor"], y=df_top["nome"],
        orientation="h",
        marker_color="#4C78A8", marker_line_width=0,
        text=[f"{v:.0f} h" for v in df_top["hs_nor"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Horas: %{x:.0f}<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title=f"<b>Top {min(top_n, len(df_top))} Colaboradores por Horas</b>",
        margin=_MARGIN,
        xaxis=dict(title="Horas Normais", gridcolor="rgba(128,128,128,.15)"),
        yaxis=dict(title=""),
        height=max(300, len(df_top) * 30 + 80),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Benchmarking por Segmento (B2)
# ─────────────────────────────────────────────────────────────────────────────

def grafico_benchmarking_segmento(df_bench: pd.DataFrame) -> go.Figure:
    """Dual-axis: custo total por segmento (barras) + consumo médio de orçamento (linha)."""
    if df_bench.empty:
        return go.Figure()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Custo Total",
        x=df_bench["segmento"], y=df_bench["custo_total"],
        marker_color="#4C78A8", marker_line_width=0,
        yaxis="y",
        hovertemplate="<b>%{x}</b><br>Custo: R$ %{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        name="Consumo Médio (%)",
        x=df_bench["segmento"], y=df_bench["consumo_medio_pct"],
        mode="markers+lines", yaxis="y2",
        marker=dict(size=10, color="#E45756"),
        line=dict(color="#E45756", width=2),
        hovertemplate="<b>%{x}</b><br>Consumo médio: %{y:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Benchmarking por Segmento</b>",
        margin=_MARGIN, legend=_LEGEND_H,
        yaxis=dict(
            title="Custo Total (R$)", tickprefix="R$ ", tickformat=",.0f",
            gridcolor="rgba(128,128,128,.15)",
        ),
        yaxis2=dict(
            title="Consumo Médio (%)", overlaying="y", side="right",
            ticksuffix="%", showgrid=False,
        ),
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Índice de Saúde do Portfólio (B3 / B7)
# ─────────────────────────────────────────────────────────────────────────────

def grafico_saude_portfolio(df_saude: pd.DataFrame) -> go.Figure:
    """Bar chart horizontal com índice de saúde por projeto (verde/amarelo/vermelho)."""
    if df_saude.empty:
        return go.Figure()
    df_plot = df_saude.sort_values("saude").tail(LIMITE_GRAFICO)
    cores = [
        "#dc2626" if s < 50 else ("#f59e0b" if s < 80 else "#22c55e")
        for s in df_plot["saude"]
    ]
    nomes = df_plot.get("nome_projeto", df_plot.get("projeto", pd.Series(dtype=str)))
    fig = go.Figure(go.Bar(
        x=df_plot["saude"], y=nomes,
        orientation="h",
        marker_color=cores, marker_line_width=0,
        text=[str(s) for s in df_plot["saude"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Índice de Saúde: %{x}<extra></extra>",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        title="<b>Índice de Saúde do Portfólio</b>",
        margin=_MARGIN,
        xaxis=dict(range=[0, 115], gridcolor="rgba(128,128,128,.15)"),
        yaxis=dict(title=""),
        height=max(300, len(df_plot) * 28 + 80),
    )
    return fig
