"""
pdf_report.py — Geração de relatório executivo em PDF (Roadmap 5.2).

Monta um PDF em memória (BytesIO) com a visão atual filtrada:
  - Cabeçalho com título, data de geração e filtros aplicados
  - KPIs consolidados
  - Tabela de pontos de atenção (exceções)
  - Tabela de projetos (resumo)

Usa reportlab (Platypus). Retorna bytes prontos para st.download_button.
"""
import io
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)


# Paleta alinhada ao app
AZUL   = colors.HexColor("#2563eb")
CINZA  = colors.HexColor("#64748b")
VERMELHO = colors.HexColor("#dc2626")
VERDE  = colors.HexColor("#16a34a")
CINZA_CLARO = colors.HexColor("#f1f5f9")


def _estilos():
    base = getSampleStyleSheet()
    estilos = {
        "titulo": ParagraphStyle(
            "tit", parent=base["Title"], fontSize=18, textColor=AZUL,
            spaceAfter=4,
        ),
        "subtitulo": ParagraphStyle(
            "sub", parent=base["Normal"], fontSize=9, textColor=CINZA,
            spaceAfter=10,
        ),
        "secao": ParagraphStyle(
            "sec", parent=base["Heading2"], fontSize=12, textColor=colors.HexColor("#1e293b"),
            spaceBefore=12, spaceAfter=6,
        ),
        "normal": ParagraphStyle(
            "norm", parent=base["Normal"], fontSize=9,
        ),
        "rodape": ParagraphStyle(
            "rod", parent=base["Normal"], fontSize=7, textColor=CINZA,
        ),
    }
    return estilos


def _fmt_brl(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def gerar_relatorio_pdf(
    df,
    titulo_pagina: str,
    filtros: dict,
    excecoes: dict,
    incluir_status: bool = True,
) -> bytes:
    """
    Gera o PDF e retorna os bytes.

    df: dataframe filtrado (uma linha por projeto)
    titulo_pagina: nome da origem (ex: "Dashboard Financeiro")
    filtros: dict com os filtros aplicados (para registrar no cabeçalho)
    excecoes: dict de detectar_excecoes()
    incluir_status: inclui coluna de status na tabela de projetos
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title="Relatório de Projetos",
    )
    est = _estilos()
    story = []

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Relatório de Acompanhamento de Projetos", est["titulo"]))
    agora = datetime.now().strftime("%d/%m/%Y às %H:%M")
    story.append(Paragraph(
        f"Origem: {titulo_pagina} &nbsp;|&nbsp; Gerado em {agora}", est["subtitulo"]
    ))

    # Filtros aplicados
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

    # ── KPIs consolidados ─────────────────────────────────────────────────────
    total_custo = float(df["valor_total"].sum()) if "valor_total" in df else 0
    total_orc   = float(df["orcamento"].sum()) if "orcamento" in df else 0
    total_horas = float(df["horas_total"].sum()) if "horas_total" in df else 0
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

    # ── Pontos de atenção ─────────────────────────────────────────────────────
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

    # ── Tabela de projetos ────────────────────────────────────────────────────
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

    if incluir_status:
        larguras = [85 * mm, 48 * mm, 38 * mm, 38 * mm, 18 * mm, 20 * mm]
    else:
        larguras = [110 * mm, 45 * mm, 45 * mm, 22 * mm, 25 * mm]

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
        ("ALIGN", (-3, 1), (-1, -1), "RIGHT"),  # números à direita
    ]
    # Colore o % de estouro em vermelho
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


def gerar_relatorio_risco_pdf(df_risco, filtros: dict) -> bytes:
    """
    Gera o PDF da Visão Executiva (risco de portfólio) e retorna os bytes.

    df_risco: saída de calcular_risco_portfolio (uma linha por projeto,
              colunas: projeto, nome_projeto, nivel_risco, motivos,
              pct_projetado, dias_atraso_max, orcamento, realizado,
              proxima_fase, proxima_fase_data)
    filtros: dict com os filtros aplicados (para registrar no cabeçalho)
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

    story.append(Paragraph("Projetos em Risco (Alto / Médio)", est["secao"]))
    destaque = df_risco[df_risco["nivel_risco"].isin(["alto", "medio"])]

    if destaque.empty:
        story.append(Paragraph(
            "Nenhum projeto em risco alto ou médio nos filtros selecionados.",
            est["normal"]
        ))
    else:
        cab = ["Projeto", "Risco", "Orçamento", "% Projetado", "Realizado", "Próxima Fase", "Motivos"]
        risco_data = [cab]
        for _, row in destaque.iterrows():
            nome = str(row.get("nome_projeto", row.get("projeto", "—")))
            risco_label = "Alto" if row["nivel_risco"] == "alto" else "Médio"
            orcamento = _fmt_brl(row.get("orcamento", 0))
            pct = row.get("pct_projetado")
            pct_str = f"{pct:.0f}%" if pd.notna(pct) else "—"
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
                realizado,
                Paragraph(fase_str, est["normal"]),
                Paragraph(motivos_str, est["normal"]),
            ])

        larguras = [42 * mm, 16 * mm, 28 * mm, 22 * mm, 28 * mm, 38 * mm, 93 * mm]
        risco_tbl = Table(risco_data, colWidths=larguras, repeatRows=1)
        estilo_risco = [
            ("BACKGROUND", (0, 0), (-1, 0), AZUL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CINZA_CLARO]),
        ]
        for i, row in enumerate(destaque["nivel_risco"].tolist(), start=1):
            if row == "alto":
                estilo_risco.append(("TEXTCOLOR", (1, i), (1, i), VERMELHO))
                estilo_risco.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
        risco_tbl.setStyle(TableStyle(estilo_risco))
        story.append(risco_tbl)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"{n_baixo} projeto(s) em baixo risco não detalhados aqui — ver exportação CSV para a lista completa.",
        est["normal"]
    ))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Relatório gerado automaticamente pelo Dashboard de Projetos. "
        "Valores baseados nos dados importados até a data de geração.",
        est["rodape"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
