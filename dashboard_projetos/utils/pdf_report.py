"""
pdf_report.py — Geração de relatório executivo em PDF.

Usa reportlab (Platypus) + matplotlib (gráficos embutidos como PNG).
Retorna bytes prontos para st.download_button.
"""
import io
from datetime import datetime, timedelta

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    Image as RLImage,
)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    _MPL_OK = True
except ImportError:
    _MPL_OK = False


# ── Paleta ───────────────────────────────────────────────────────────────────
AZUL        = colors.HexColor("#2563eb")
CINZA       = colors.HexColor("#64748b")
VERMELHO    = colors.HexColor("#dc2626")
VERDE       = colors.HexColor("#16a34a")
CINZA_CLARO = colors.HexColor("#f1f5f9")
AMARELO_TBL = colors.HexColor("#b45309")

# Paleta matplotlib (tema claro — legível em PDF impresso)
_BG    = "#ffffff"
_GRID  = "#cbd5e1"
_TEXT  = "#1e293b"
_VERDE_M  = "#16a34a"
_VERM_M   = "#dc2626"
_AMAR_M   = "#d97706"
_AZUL_M   = "#2563eb"
_CINZ_M   = "#64748b"
_AMAR2_M  = "#b45309"


# ── Helpers ───────────────────────────────────────────────────────────────────
def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "tit", parent=base["Title"], fontSize=18, textColor=AZUL, spaceAfter=4,
        ),
        "subtitulo": ParagraphStyle(
            "sub", parent=base["Normal"], fontSize=9, textColor=CINZA, spaceAfter=10,
        ),
        "secao": ParagraphStyle(
            "sec", parent=base["Heading2"], fontSize=12,
            textColor=colors.HexColor("#1e293b"), spaceBefore=12, spaceAfter=6,
        ),
        "proj_header": ParagraphStyle(
            "ph", parent=base["Heading3"], fontSize=10,
            textColor=colors.HexColor("#1e293b"), spaceBefore=8, spaceAfter=4,
        ),
        "normal": ParagraphStyle("norm", parent=base["Normal"], fontSize=9),
        "rodape": ParagraphStyle(
            "rod", parent=base["Normal"], fontSize=7, textColor=CINZA,
        ),
    }


def _fmt_brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def _parse_dt(val):
    if not val or str(val) in ("0", "None", "nan", ""):
        return None
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d")
    except Exception:
        return None


def _fig_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=_BG, edgecolor="#cbd5e1")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── Gráfico de Marcos ─────────────────────────────────────────────────────────
_MARCOS_DEF = [
    ("Viabilidade",         "prev_viabilidade",      "real_viabilidade"),
    ("Qualidade",           "prev_qualidade",         "real_qualidade"),
    ("Aprov. Lançamento",   "prev_aprov_lancamento",  "real_aprov_lancamento"),
    ("Lançamento",          "prev_lancamento",        "real_lancamento"),
]


def _png_marcos(row, nome_projeto: str):
    if not _MPL_OK:
        return None
    tem = any(_parse_dt(row.get(p)) or _parse_dt(row.get(r)) for _, p, r in _MARCOS_DEF)
    if not tem:
        return None

    hoje = datetime.today()
    fig, ax = plt.subplots(figsize=(10.5, 2.6))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)

    handles, labels_seen = {}, set()
    all_x_dates = {hoje}

    for i, (label, cp, cr) in enumerate(_MARCOS_DEF):
        prev_d = _parse_dt(row.get(cp))
        real_d = _parse_dt(row.get(cr))

        if prev_d:
            all_x_dates.add(prev_d)
            h = ax.scatter(prev_d, i, marker="D", color=_CINZ_M, s=60, zorder=5)
            if "Previsto" not in labels_seen:
                handles["Previsto"] = h; labels_seen.add("Previsto")

        if real_d:
            all_x_dates.add(real_d)
            atrasado = prev_d is not None and real_d > prev_d
            cor = _VERM_M if atrasado else _VERDE_M
            lbl = "Realizado (atraso)" if atrasado else "Realizado"
            h = ax.scatter(real_d, i, marker="o", color=cor, s=80, zorder=6)
            if lbl not in labels_seen:
                handles[lbl] = h; labels_seen.add(lbl)
            if prev_d and atrasado:
                ax.plot([prev_d, real_d], [i, i], color=_VERM_M,
                        linewidth=1.2, alpha=0.5, zorder=3)
        elif prev_d and prev_d < hoje:
            h = ax.scatter(hoje, i, marker=">", color=_AMAR_M, s=70, zorder=6)
            if "Em atraso" not in labels_seen:
                handles["Em atraso"] = h; labels_seen.add("Em atraso")
            ax.plot([prev_d, hoje], [i, i], color=_AMAR_M,
                    linewidth=1.2, alpha=0.45, linestyle="--", zorder=3)

    ax.axvline(hoje, color=_CINZ_M, linewidth=0.8, linestyle=":", alpha=0.6)

    ax.set_yticks(range(len(_MARCOS_DEF)))
    ax.set_yticklabels([m[0] for m in _MARCOS_DEF], color=_TEXT, fontsize=8)

    # Eixo X: mostrar data de cada ponto plotado
    sorted_dates = sorted(all_x_dates)
    ax.set_xticks(sorted_dates)
    ax.set_xticklabels([d.strftime("%d/%m/%y") for d in sorted_dates],
                       rotation=45, ha="right", fontsize=7, color=_TEXT)

    for sp in ax.spines.values():
        sp.set_edgecolor(_GRID)
    ax.tick_params(colors=_TEXT)
    ax.grid(axis="x", color=_GRID, alpha=0.45, linewidth=0.5)
    ax.set_title(f"Marcos — {nome_projeto}", color=_TEXT, fontsize=9, pad=6, loc="left")
    if handles:
        ax.legend(handles.values(), handles.keys(),
                  facecolor=_BG, edgecolor=_GRID, labelcolor=_TEXT,
                  fontsize=7, loc="lower right", ncol=len(handles))
    fig.tight_layout(pad=0.5)
    return _fig_bytes(fig)


# ── Gráfico de Burn de Custo ──────────────────────────────────────────────────
def _png_burn(row, df_custos_raw, nome_projeto: str):
    if not _MPL_OK or df_custos_raw is None or df_custos_raw.empty:
        return None
    if "centro_de_custo" not in df_custos_raw.columns:
        return None

    projeto = str(row.get("projeto", ""))
    ccs = [c.strip() for c in projeto.split(",")]
    df_c = df_custos_raw[df_custos_raw["centro_de_custo"].isin(ccs)].copy()
    if df_c.empty or "mes_ref" not in df_c.columns:
        return None

    val_col = "realizado" if "realizado" in df_c.columns else "valor"
    if val_col not in df_c.columns:
        return None

    gasto_mes = (
        df_c.groupby("mes_ref")[val_col].sum()
        .reset_index().sort_values("mes_ref")
        .rename(columns={val_col: "gasto"})
    )
    gasto_mes = gasto_mes[gasto_mes["gasto"] != 0].copy()
    if gasto_mes.empty:
        return None

    gasto_mes["acumulado"] = gasto_mes["gasto"].cumsum()
    try:
        gasto_mes["mes_dt"] = pd.to_datetime(gasto_mes["mes_ref"] + "-01")
    except Exception:
        return None

    # Import inline to avoid circular-import risk
    from utils.data_processor import projecao_burn_rate
    burn = projecao_burn_rate(row, df_c)

    fig, ax = plt.subplots(figsize=(10.5, 2.6))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_BG)

    xs = gasto_mes["mes_dt"]
    ys = gasto_mes["acumulado"]
    ax.fill_between(xs, ys, alpha=0.18, color=_AZUL_M)
    ax.plot(xs, ys, color=_AZUL_M, linewidth=2,
            marker="o", markersize=3, label="Realizado acumulado")

    if burn["status"] == "projetado" and burn["meses_restantes"] > 0:
        hoje = datetime.today()
        ultimo_mes  = gasto_mes["mes_ref"].iloc[-1]
        ultimo_acum = float(ys.iloc[-1])
        proj_x = [pd.Timestamp(ultimo_mes + "-01")]
        proj_y = [ultimo_acum]
        for k in range(1, burn["meses_restantes"] + 1):
            m_abs = hoje.month + k
            y_p   = hoje.year + (m_abs - 1) // 12
            m_p   = (m_abs - 1) % 12 + 1
            proj_x.append(pd.Timestamp(f"{y_p}-{m_p:02d}-01"))
            proj_y.append(ultimo_acum + burn["ritmo_mensal"] * k)
        ax.plot(proj_x, proj_y, color=_AMAR2_M, linewidth=1.8,
                linestyle="--", label="Projeção (burn rate)", alpha=0.9)

    orc = float(row.get("orcamento", 0) or 0)
    if orc > 0:
        ax.axhline(orc, color=_VERM_M, linewidth=1.2, linestyle=":",
                   alpha=0.8, label=f"Orçamento: R$ {orc:,.0f}")

    xform = ax.get_xaxis_transform()
    prev_lanc = _parse_dt(row.get("prev_lancamento"))
    if prev_lanc:
        ax.axvline(prev_lanc, color=_VERDE_M, linewidth=1,
                   linestyle=":", alpha=0.7)
        ax.text(prev_lanc, 0.96, "  Prev.", color=_VERDE_M,
                fontsize=7, va="top", transform=xform)

    data_conc = burn.get("data_conclusao_estimada")
    dias_atr  = burn.get("dias_atraso_confirmado", 0)
    if data_conc is not None and dias_atr > 0:
        dc_dt = datetime(data_conc.year, data_conc.month, data_conc.day)
        if prev_lanc is None or dc_dt != prev_lanc:
            ax.axvline(dc_dt, color=_VERM_M, linewidth=1,
                       linestyle="--", alpha=0.7)
            ax.text(dc_dt, 0.82, f"  +{dias_atr}d", color=_VERM_M,
                    fontsize=7, va="top", transform=xform)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b/%Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right",
             color=_TEXT, fontsize=7.5)
    ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"R${v/1000:.0f}k" if v >= 1000 else f"R${v:.0f}")
    )
    ax.tick_params(colors=_TEXT, labelsize=8)
    for sp in ax.spines.values():
        sp.set_edgecolor(_GRID)
    ax.grid(color=_GRID, alpha=0.4, linewidth=0.5)
    ax.set_title(f"Burn de Custo — {nome_projeto}", color=_TEXT,
                 fontsize=9, pad=6, loc="left")
    ax.legend(facecolor=_BG, edgecolor=_GRID, labelcolor=_TEXT,
              fontsize=7, loc="upper left")
    fig.tight_layout(pad=0.5)
    return _fig_bytes(fig)


# ── Relatório de Acompanhamento (página Andamento) ────────────────────────────
def gerar_relatorio_pdf(
    df,
    titulo_pagina: str,
    filtros: dict,
    excecoes: dict,
    incluir_status: bool = True,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title="Relatório de Projetos",
    )
    est = _estilos()
    story = []

    story.append(Paragraph("Relatório de Acompanhamento de Projetos", est["titulo"]))
    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")
    story.append(Paragraph(
        f"Origem: {titulo_pagina} &nbsp;|&nbsp; Gerado em {agora}", est["subtitulo"]
    ))

    partes_filtro = []
    for chave, valores in filtros.items():
        if valores and isinstance(valores, (list, tuple)):
            if len(valores) <= 4:
                partes_filtro.append(f"<b>{chave}:</b> {', '.join(map(str, valores))}")
            else:
                partes_filtro.append(f"<b>{chave}:</b> {len(valores)} selecionados")
    if partes_filtro:
        story.append(Paragraph(" &nbsp;·&nbsp; ".join(partes_filtro), est["normal"]))
    story.append(Spacer(1, 8))

    total_custo = float(df["valor_total"].sum()) if "valor_total" in df else 0
    total_orc   = float(df["orcamento"].sum())   if "orcamento"   in df else 0
    total_horas = float(df["horas_total"].sum())  if "horas_total" in df else 0
    saldo       = total_orc - total_custo
    n_proj      = len(df)

    kpi_data = [
        ["Projetos", "Orçamento Total", "Realizado Total", "Saldo", "Horas Totais"],
        [
            str(n_proj),
            _fmt_brl(total_orc) if total_orc > 0 else "N/D",
            _fmt_brl(total_custo),
            _fmt_brl(saldo) if total_orc > 0 else "N/D",
            f"{total_horas:,.0f} h".replace(",", "."),
        ],
    ]
    kpi_tbl = Table(kpi_data, colWidths=[50 * mm] * 5)
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, 1), (-1, 1), CINZA_CLARO),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Pontos de Atenção", est["secao"]))
    linhas_exc = []
    if excecoes.get("estouro"):
        linhas_exc.append(["Acima do orçamento", str(len(excecoes["estouro"])),
                           ", ".join(excecoes["estouro"][:8]) + ("…" if len(excecoes["estouro"]) > 8 else "")])
    if excecoes.get("atrasados"):
        linhas_exc.append(["Lançamento atrasado", str(len(excecoes["atrasados"])),
                           ", ".join(excecoes["atrasados"][:8]) + ("…" if len(excecoes["atrasados"]) > 8 else "")])
    if excecoes.get("stand_by"):
        linhas_exc.append(["Em Stand by", str(len(excecoes["stand_by"])),
                           ", ".join(excecoes["stand_by"][:8]) + ("…" if len(excecoes["stand_by"]) > 8 else "")])
    if excecoes.get("cancelados"):
        linhas_exc.append(["Cancelados", str(len(excecoes["cancelados"])),
                           ", ".join(excecoes["cancelados"][:8]) + ("…" if len(excecoes["cancelados"]) > 8 else "")])

    if linhas_exc:
        exc_data = [["Categoria", "Qtde", "Projetos"]] + linhas_exc
        exc_tbl = Table(exc_data, colWidths=[45 * mm, 18 * mm, 204 * mm])
        exc_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VERMELHO),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
        ]))
        story.append(exc_tbl)
    else:
        story.append(Paragraph(
            "Nenhuma exceção detectada — todos os projetos dentro do previsto.",
            est["normal"]
        ))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Resumo por Projeto", est["secao"]))
    cab = ["Projeto", "Status", "Realizado", "Orçamento", "% Orç.", "Horas"] if incluir_status \
          else ["Projeto", "Realizado", "Orçamento", "% Orç.", "Horas"]
    proj_data = [cab]
    df_ord = df.sort_values("valor_total", ascending=False) if "valor_total" in df else df
    for _, row in df_ord.iterrows():
        nome = str(row.get("nome_projeto", row.get("projeto", "—")))[:48]
        realizado = _fmt_brl(row.get("valor_total", 0))
        orc_v = row.get("orcamento", 0) or 0
        orcamento = _fmt_brl(orc_v) if orc_v > 0 else "N/D"
        pct = row.get("pct_orcamento", 0)
        pct_str = f"{pct:.0f}%" if orc_v > 0 else "—"
        horas = f"{row.get('horas_total', 0):,.0f}".replace(",", ".")
        if incluir_status:
            status = str(row.get("status_projeto", "—"))
            proj_data.append([nome, status, realizado, orcamento, pct_str, horas])
        else:
            proj_data.append([nome, realizado, orcamento, pct_str, horas])

    larguras = [85 * mm, 48 * mm, 38 * mm, 38 * mm, 18 * mm, 20 * mm] if incluir_status \
               else [110 * mm, 45 * mm, 45 * mm, 22 * mm, 25 * mm]
    proj_tbl = Table(proj_data, colWidths=larguras, repeatRows=1)
    estilo_proj = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
        ("ALIGN", (-3, 1), (-1, -1), "RIGHT"),
    ]
    col_pct = 4 if incluir_status else 3
    for i, row in enumerate(proj_data[1:], start=1):
        try:
            pv = float(str(row[col_pct]).replace("%", "").strip())
            if pv > 100:
                estilo_proj.append(("TEXTCOLOR", (col_pct, i), (col_pct, i), VERMELHO))
                estilo_proj.append(("FONTNAME", (col_pct, i), (col_pct, i), "Helvetica-Bold"))
        except Exception:
            pass
    proj_tbl.setStyle(TableStyle(estilo_proj))
    story.append(proj_tbl)
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Relatório gerado automaticamente pelo Dashboard de Projetos. "
        "Valores baseados nos dados importados até a data de geração.",
        est["rodape"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ── Relatório de Visão Executiva ──────────────────────────────────────────────
def gerar_relatorio_risco_pdf(
    df_risco: pd.DataFrame,
    filtros: dict,
    df_dashboard: pd.DataFrame = None,
    df_custos_raw: pd.DataFrame = None,
) -> bytes:
    """
    Gera o PDF da Visão Executiva com:
      - KPIs de risco
      - Tabela de projetos em risco (alto/médio)
      - Por projeto: gráfico de marcos + gráfico de burn de custo
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title="Relatório de Visão Executiva",
    )
    est = _estilos()
    story = []

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Visão Executiva — Risco de Portfólio", est["titulo"]))
    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")
    story.append(Paragraph(f"Gerado em {agora}", est["subtitulo"]))

    partes_filtro = []
    for chave, valores in filtros.items():
        if valores and isinstance(valores, (list, tuple)):
            if len(valores) <= 4:
                partes_filtro.append(f"<b>{chave}:</b> {', '.join(map(str, valores))}")
            else:
                partes_filtro.append(f"<b>{chave}:</b> {len(valores)} selecionados")
    if partes_filtro:
        story.append(Paragraph(" &nbsp;·&nbsp; ".join(partes_filtro), est["normal"]))
    story.append(Spacer(1, 8))

    # ── KPIs ──────────────────────────────────────────────────────────────────
    n_alto  = int((df_risco["nivel_risco"] == "alto").sum())
    n_medio = int((df_risco["nivel_risco"] == "medio").sum())
    n_baixo = int((df_risco["nivel_risco"] == "baixo").sum())

    kpi_data = [
        ["Alto risco", "Risco médio", "Baixo risco"],
        [str(n_alto), str(n_medio), str(n_baixo)],
    ]
    kpi_tbl = Table(kpi_data, colWidths=[50 * mm] * 3)
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, 1), (-1, 1), CINZA_CLARO),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 12))

    # ── Tabela resumo de riscos ────────────────────────────────────────────────
    story.append(Paragraph("Projetos em Risco (Alto / Médio)", est["secao"]))
    destaque = df_risco[df_risco["nivel_risco"].isin(["alto", "medio"])].copy()

    if destaque.empty:
        story.append(Paragraph(
            "Nenhum projeto em risco alto ou médio nos filtros selecionados.",
            est["normal"]
        ))
    else:
        cab = ["Projeto", "Risco", "Orçamento", "% Projetado",
               "Atraso (d)", "Realizado", "Próxima Fase", "Motivos"]
        risco_data = [cab]
        for _, row in destaque.iterrows():
            nome = str(row.get("nome_projeto", row.get("projeto", "—")))
            risco_label = "Alto" if row["nivel_risco"] == "alto" else "Médio"
            orcamento = _fmt_brl(row.get("orcamento", 0))
            pct = row.get("pct_projetado")
            pct_str = f"{pct:.0f}%" if pd.notna(pct) else "—"
            atraso = row.get("dias_atraso_max", 0)
            atraso_str = f"{int(atraso)}d" if atraso > 0 else "—"
            realizado = _fmt_brl(row.get("realizado", 0))
            if pd.notna(row.get("proxima_fase")):
                fase_str = f"{row['proxima_fase']} ({row['proxima_fase_data'].strftime('%d/%m/%Y')})"
            else:
                fase_str = "Concluído"
            motivos_str = "; ".join(row.get("motivos") or []) or "—"
            risco_data.append([
                Paragraph(nome, est["normal"]),
                risco_label,
                orcamento,
                pct_str,
                atraso_str,
                realizado,
                Paragraph(fase_str, est["normal"]),
                Paragraph(motivos_str, est["normal"]),
            ])

        larguras = [38 * mm, 15 * mm, 26 * mm, 20 * mm, 15 * mm,
                    26 * mm, 35 * mm, 92 * mm]
        risco_tbl = Table(risco_data, colWidths=larguras, repeatRows=1)
        estilo_risco = [
            ("BACKGROUND", (0, 0), (-1, 0), AZUL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (2, 1), (5, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
        ]
        for i, (_, row_r) in enumerate(destaque.iterrows(), start=1):
            if row_r["nivel_risco"] == "alto":
                estilo_risco.append(("TEXTCOLOR", (1, i), (1, i), VERMELHO))
                estilo_risco.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
            try:
                pv = float(str(risco_data[i][3]).replace("%", "").strip())
                if pv > 100:
                    estilo_risco.append(("TEXTCOLOR", (3, i), (3, i), VERMELHO))
                    estilo_risco.append(("FONTNAME", (3, i), (3, i), "Helvetica-Bold"))
            except Exception:
                pass
            try:
                av = int(str(risco_data[i][4]).replace("d", "").strip())
                if av > 0:
                    estilo_risco.append(("TEXTCOLOR", (4, i), (4, i), AMARELO_TBL))
                    estilo_risco.append(("FONTNAME", (4, i), (4, i), "Helvetica-Bold"))
            except Exception:
                pass
        risco_tbl.setStyle(TableStyle(estilo_risco))
        story.append(risco_tbl)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"{n_baixo} projeto(s) em baixo risco não detalhados aqui — "
        "ver exportação CSV para a lista completa.",
        est["normal"]
    ))

    # ── Gráficos por projeto ───────────────────────────────────────────────────
    if not destaque.empty and _MPL_OK:
        # Monta índice proj_id → row do df_dashboard (para datas de marcos)
        dash_idx = {}
        if df_dashboard is not None and not df_dashboard.empty and "projeto" in df_dashboard.columns:
            for _, dr in df_dashboard.iterrows():
                dash_idx[str(dr["projeto"])] = dr

        for i, (_, risco_row) in enumerate(destaque.iterrows()):
            story.append(PageBreak())
            if i == 0:
                story.append(Paragraph("Detalhe por Projeto", est["secao"]))

            proj_id   = str(risco_row["projeto"])
            nome      = str(risco_row["nome_projeto"])
            nivel     = risco_row["nivel_risco"]
            icone_txt = "Alto risco" if nivel == "alto" else "Risco médio"

            story.append(Paragraph(f"{nome} — {icone_txt}", est["proj_header"]))

            dash_row = dash_idx.get(proj_id)

            # Gráfico de marcos
            if dash_row is not None:
                png = _png_marcos(dash_row, nome)
                if png:
                    story.append(RLImage(io.BytesIO(png), width=267 * mm, height=60 * mm))
                    story.append(Spacer(1, 4))

            # Gráfico de burn
            burn_row = dash_row if dash_row is not None else risco_row
            if df_custos_raw is not None and not df_custos_raw.empty:
                png = _png_burn(burn_row, df_custos_raw, nome)
                if png:
                    story.append(RLImage(io.BytesIO(png), width=267 * mm, height=70 * mm))

    # ── Rodapé ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Relatório gerado automaticamente pelo Dashboard de Projetos. "
        "Valores baseados nos dados importados até a data de geração.",
        est["rodape"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
