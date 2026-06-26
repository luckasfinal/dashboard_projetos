"""
dashboard_executivo.py — lógica de negócio para o Dashboard Executivo.
Funções puras: recebem DataFrames, retornam DataFrames/dicts. Sem Streamlit.
"""
from __future__ import annotations

import pandas as pd
from datetime import datetime, date, timedelta

# ─────────────────────────────────────────────
# Categorização de contas
# ─────────────────────────────────────────────

PALAVRAS_CATEGORIA: dict[str, list[str]] = {
    "Mão de obra": ["mão de obra", "mao de obra", "salario", "salário", "pessoal", "folha", "rh"],
    "Terceiros":   ["terceiro", "serviço", "servico", "contratado", "consultoria", "fornecedor"],
    "Materiais":   ["material", "componente", "insumo", "peça", "peca", "estoque"],
    "Viagens":     ["viagem", "hospedagem", "transporte", "diária", "diaria", "deslocamento"],
}

CATEGORIAS_CUSTO: list[str] = list(PALAVRAS_CATEGORIA.keys())


def categorizar_conta(conta) -> str:
    """Retorna categoria de custo pela descrição textual do campo conta."""
    if conta is None or (isinstance(conta, float) and pd.isna(conta)) or str(conta).strip() == "":
        return "Outras"
    conta_lower = str(conta).lower()
    for categoria, palavras in PALAVRAS_CATEGORIA.items():
        if any(p in conta_lower for p in palavras):
            return categoria
    return "Outras"


# ─────────────────────────────────────────────
# Marcos
# ─────────────────────────────────────────────

MARCOS_CONFIG: list[tuple[str, str, str, float]] = [
    ("prev_viabilidade",      "real_viabilidade",      "Viabilidade",            0.45),
    ("prev_qualidade",        "real_qualidade",        "Qualidade",               0.40),
    ("prev_aprov_lancamento", "real_aprov_lancamento", "Aprovação p/ Lançamento", 0.05),
    ("prev_lancamento",       "real_lancamento",       "Lançamento",              0.10),
]

_MARCOS_OBS_COL: dict[str, str] = {
    "Viabilidade":             "obs_viabilidade",
    "Qualidade":               "obs_qualidade",
    "Aprovação p/ Lançamento": "obs_aprov_lancamento",
    "Lançamento":              "obs_lancamento",
}


def _parse_data(val) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if s in ("", "0", "None", "nan"):
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def calcular_marcos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expande df (1 projeto/linha) em DataFrame de marcos (4 linhas/projeto).
    Colunas: projeto, nome_projeto, marco, peso, data_prevista, data_realizada,
             desvio_dias, status_marco, concluido
    """
    hoje = datetime.today().date()
    linhas: list[dict] = []
    for _, row in df.iterrows():
        for col_prev, col_real, label, peso in MARCOS_CONFIG:
            prev_d = _parse_data(row.get(col_prev))
            real_d = _parse_data(row.get(col_real))
            concluido = bool(real_d is not None)
            if concluido:
                desvio = (real_d - prev_d).days if prev_d else 0
                status = "Atrasado" if desvio > 0 else "Concluído"
            elif prev_d is not None:
                desvio = (hoje - prev_d).days
                status = "Atrasado" if desvio > 0 else "Pendente"
            else:
                desvio, status = 0, "Pendente"
            obs_raw = row.get(_MARCOS_OBS_COL.get(label, ""), "")
            if obs_raw is None or (isinstance(obs_raw, float) and pd.isna(obs_raw)):
                obs_raw = ""
            linhas.append({
                "projeto":        row.get("projeto"),
                "nome_projeto":   row.get("nome_projeto", row.get("projeto")),
                "marco":          label,
                "peso":           peso,
                "data_prevista":  prev_d,
                "data_realizada": real_d,
                "desvio_dias":    desvio,
                "status_marco":   status,
                "concluido":      concluido,
                "observacao":     str(obs_raw).strip(),
            })
    result = pd.DataFrame(linhas)
    if "concluido" in result.columns:
        result["concluido"] = result["concluido"].astype(object)
    return result


# ─────────────────────────────────────────────
# Burn Rate (Seção 8)
# ─────────────────────────────────────────────

def calcular_burn_rate(df_custos_f: pd.DataFrame) -> pd.DataFrame:
    if df_custos_f.empty or "mes_ref" not in df_custos_f.columns:
        return pd.DataFrame(columns=["projeto", "mes_ref", "custo_mensal", "custo_acumulado", "burn_rate"])
    df = (
        df_custos_f.groupby(["centro_de_custo", "mes_ref"])["realizado"]
        .sum().reset_index()
        .rename(columns={"centro_de_custo": "projeto", "realizado": "custo_mensal"})
        .sort_values(["projeto", "mes_ref"])
    )
    df["custo_acumulado"] = df.groupby("projeto")["custo_mensal"].cumsum()
    df["_n"] = df.groupby("projeto").cumcount() + 1
    df["burn_rate"] = df["custo_acumulado"] / df["_n"]
    return df.drop(columns=["_n"])


# ─────────────────────────────────────────────
# Forecast de Prazo (Seção 9)
# ─────────────────────────────────────────────

def calcular_forecast_prazo(df_f: pd.DataFrame, df_marcos: pd.DataFrame) -> pd.DataFrame:
    atraso_medio = (
        df_marcos[df_marcos["concluido"] & (df_marcos["desvio_dias"] > 0)]
        .groupby("projeto")["desvio_dias"].mean().round()
    )
    linhas: list[dict] = []
    for _, row in df_f.iterrows():
        proj = row["projeto"]
        prev_lanc = _parse_data(row.get("prev_lancamento"))
        atraso_d = int(atraso_medio.get(proj, 0) or 0)
        forecast = (prev_lanc + timedelta(days=atraso_d)) if prev_lanc else None
        linhas.append({
            "nome_projeto":      row.get("nome_projeto", proj),
            "data_planejada":    prev_lanc,
            "atraso_medio_dias": atraso_d,
            "forecast":          forecast,
            "desvio_total":      atraso_d,
        })
    return pd.DataFrame(linhas)


# ─────────────────────────────────────────────
# Forecast de Custo / EAC (Seção 10)
# ─────────────────────────────────────────────

def calcular_forecast_custo(df_f: pd.DataFrame, df_marcos: pd.DataFrame) -> pd.DataFrame:
    pct_por_proj = (
        df_marcos[df_marcos["concluido"]].groupby("projeto")["peso"].sum()
    )
    linhas: list[dict] = []
    for _, row in df_f.iterrows():
        proj  = row["projeto"]
        custo = float(row.get("valor_total", 0) or 0)
        orc   = float(row.get("orcamento", 0) or 0)
        pct   = float(pct_por_proj.get(proj, 0) or 0)
        eac   = (custo / pct) if pct > 0 else None
        desvio = ((eac - orc) / orc * 100) if (eac is not None and orc > 0) else None
        linhas.append({
            "nome_projeto":   row.get("nome_projeto", proj),
            "custo_atual":    custo,
            "pct_concluido":  pct,
            "eac":            eac,
            "orcamento":      orc,
            "desvio_eac_pct": desvio,
            "cpi":            _cpi(custo, orc, pct),
        })
    return pd.DataFrame(linhas)


# ─────────────────────────────────────────────
# Matriz Executiva Prazo × Custo (Seção 11)
# ─────────────────────────────────────────────

def calcular_matriz_prazo_custo(
    df_forecast_prazo: pd.DataFrame,
    df_forecast_custo: pd.DataFrame,
) -> pd.DataFrame:
    df = (
        df_forecast_prazo[["nome_projeto", "desvio_total"]]
        .rename(columns={"desvio_total": "desvio_prazo_dias"})
        .merge(df_forecast_custo[["nome_projeto", "desvio_eac_pct"]], on="nome_projeto", how="inner")
        .dropna(subset=["desvio_eac_pct"])
    )
    if df.empty:
        return df.assign(quadrante=pd.Series(dtype=str))

    def _quad(row) -> str:
        x, y = row["desvio_prazo_dias"], row["desvio_eac_pct"]
        if x <= 0 and y <= 0: return "Controlado"
        if x > 0  and y <= 0: return "Risco de Prazo"
        if x <= 0 and y > 0:  return "Risco de Custo"
        return "Crítico"

    df["quadrante"] = df.apply(_quad, axis=1)
    return df


# ─────────────────────────────────────────────
# Resumo Executivo (Seção 1)
# ─────────────────────────────────────────────

_STATUS_TERMINAIS = {"Cancelado", "Lançado"}


def calcular_resumo_executivo(
    df_f: pd.DataFrame,
    df_custos_f: pd.DataFrame,
    df_horas_f: pd.DataFrame,
    df_marcos: pd.DataFrame,
) -> dict:
    if "status_projeto" in df_f.columns:
        projetos_ativos = int(
            df_f["status_projeto"].apply(lambda s: str(s).strip() not in _STATUS_TERMINAIS).sum()
        )
    else:
        projetos_ativos = len(df_f)

    atrasados_set = set(df_marcos[df_marcos["status_marco"] == "Atrasado"]["projeto"].unique())
    projetos_com_atraso = len(atrasados_set & set(df_f["projeto"].unique()))

    horas  = float(df_horas_f["hs_nor"].sum())  if (not df_horas_f.empty  and "hs_nor"    in df_horas_f.columns)  else 0.0
    custos = float(df_custos_f["realizado"].sum()) if (not df_custos_f.empty and "realizado" in df_custos_f.columns) else 0.0

    pct_s = (
        df_marcos[df_marcos["concluido"]].groupby("projeto")["peso"].sum()
        .reindex(df_f["projeto"].unique()).fillna(0.0)
    )
    pct_medio = float(pct_s.mean()) if not pct_s.empty else 0.0

    atrasos = df_marcos[df_marcos["concluido"] & (df_marcos["desvio_dias"] > 0)]["desvio_dias"]
    prazo_medio = float(atrasos.mean()) if not atrasos.empty else 0.0

    return {
        "projetos_ativos":     projetos_ativos,
        "projetos_com_atraso": projetos_com_atraso,
        "horas_consumidas":    horas,
        "custos_acumulados":   custos,
        "pct_medio_conclusao": pct_medio,
        "prazo_medio_atraso":  prazo_medio,
    }


# ─────────────────────────────────────────────
# Status Geral dos Projetos (Seção 2)
# ─────────────────────────────────────────────

def calcular_status_projetos(
    df_f: pd.DataFrame,
    df_marcos: pd.DataFrame,
    df_custos_f: pd.DataFrame,
    df_horas_f: pd.DataFrame,
) -> pd.DataFrame:
    pct = (
        df_marcos[df_marcos["concluido"]].groupby("projeto")["peso"].sum()
        .reset_index().rename(columns={"peso": "pct_concluido"})
    )
    marcos_ok = (
        df_marcos[df_marcos["concluido"]].groupby("projeto").size()
        .reset_index(name="marcos_concluidos")
    )
    atraso = (
        df_marcos[df_marcos["status_marco"] == "Atrasado"]
        .groupby("projeto")["desvio_dias"].mean()
        .reset_index().rename(columns={"desvio_dias": "atraso_medio_dias"})
    )
    horas_p = pd.DataFrame(columns=["projeto", "horas_total"])
    if not df_horas_f.empty and "c_custo" in df_horas_f.columns:
        horas_p = (
            df_horas_f.groupby("c_custo")["hs_nor"].sum()
            .reset_index().rename(columns={"c_custo": "projeto", "hs_nor": "horas_total"})
        )
    custos_p = pd.DataFrame(columns=["projeto", "custo_total"])
    if not df_custos_f.empty and "centro_de_custo" in df_custos_f.columns:
        custos_p = (
            df_custos_f.groupby("centro_de_custo")["realizado"].sum()
            .reset_index().rename(columns={"centro_de_custo": "projeto", "realizado": "custo_total"})
        )
    cols = ["projeto", "nome_projeto"]
    if "status_projeto" in df_f.columns:
        cols.append("status_projeto")
    result = (
        df_f[cols].copy()
        .merge(pct,       on="projeto", how="left")
        .merge(marcos_ok, on="projeto", how="left")
        .merge(atraso,    on="projeto", how="left")
        .merge(horas_p,   on="projeto", how="left")
        .merge(custos_p,  on="projeto", how="left")
    )
    result["pct_concluido"]     = result["pct_concluido"].fillna(0.0)
    result["marcos_concluidos"] = result["marcos_concluidos"].fillna(0).astype(int)
    result["marcos_totais"]     = 4
    result["atraso_medio_dias"] = result["atraso_medio_dias"].fillna(0.0)
    if "horas_total" not in result.columns:
        result["horas_total"] = 0.0
    else:
        result["horas_total"] = result["horas_total"].fillna(0.0)
    if "custo_total" not in result.columns:
        result["custo_total"] = 0.0
    else:
        result["custo_total"] = result["custo_total"].fillna(0.0)
    result["status_visual"] = result["atraso_medio_dias"].apply(
        lambda a: "🟢" if a <= 0 else ("🟡" if a <= 30 else "🔴")
    )
    return result


# ─────────────────────────────────────────────
# Custos por Categoria (Seções 5, 6)
# ─────────────────────────────────────────────

def calcular_custos_por_categoria(df_custos_f: pd.DataFrame) -> pd.DataFrame:
    if df_custos_f.empty or "centro_de_custo" not in df_custos_f.columns:
        return pd.DataFrame(columns=["projeto", "categoria_custo", "total_custo"])
    df = df_custos_f.copy()
    if "categoria_custo" not in df.columns:
        df["categoria_custo"] = df.get("conta", pd.Series("", index=df.index)).apply(categorizar_conta)
    return (
        df.groupby(["centro_de_custo", "categoria_custo"])["realizado"].sum()
        .reset_index().rename(columns={"centro_de_custo": "projeto", "realizado": "total_custo"})
    )


# ─────────────────────────────────────────────
# Consumo de Recursos (Seção 7)
# ─────────────────────────────────────────────

def calcular_recursos(df_f: pd.DataFrame, df_horas_f: pd.DataFrame) -> pd.DataFrame:
    if df_horas_f.empty or "c_custo" not in df_horas_f.columns:
        return pd.DataFrame(columns=["nome_projeto", "horas_total", "n_colaboradores", "horas_por_colaborador"])
    agg = (
        df_horas_f.groupby("c_custo")
        .agg(horas_total=("hs_nor", "sum"), n_colaboradores=("nome", "nunique"))
        .reset_index().rename(columns={"c_custo": "projeto"})
    )
    agg["horas_por_colaborador"] = agg.apply(
        lambda r: r["horas_total"] / r["n_colaboradores"] if r["n_colaboradores"] > 0 else 0.0, axis=1
    )
    nomes = df_f[["projeto", "nome_projeto"]].drop_duplicates("projeto")
    return agg.merge(nomes, on="projeto", how="left")


# ─────────────────────────────────────────────
# CPI — Cost Performance Index
# ─────────────────────────────────────────────

def _cpi(custo: float, orc: float, pct: float) -> float | None:
    """CPI = BCWP / ACWP = (orc × pct) / custo. None se dados insuficientes."""
    if custo <= 0 or orc <= 0 or pct <= 0:
        return None
    return (orc * pct) / custo


def calcular_cpi_projeto(row) -> float | None:
    """
    CPI para uma linha de projeto (dict ou pd.Series).
    Usa MARCOS_CONFIG para somar os pesos dos marcos com data_realizada preenchida.
    Retorna None se custo, orçamento ou % concluído forem zero.
    """
    custo = float(row.get("valor_total", 0) or 0)
    orc   = float(row.get("orcamento", 0) or 0)
    pct   = sum(
        peso
        for _, col_real, _, peso in MARCOS_CONFIG
        if _parse_data(row.get(col_real)) is not None
    )
    return _cpi(custo, orc, pct)


# ─────────────────────────────────────────────
# Home Executiva — funções de portfólio
# ─────────────────────────────────────────────

_MARCOS_HOME: list[tuple[str, str, str]] = [
    ("prev_viabilidade",      "real_viabilidade",      "Viabilidade"),
    ("prev_qualidade",        "real_qualidade",        "Qualidade"),
    ("prev_aprov_lancamento", "real_aprov_lancamento", "Aprov. Lançamento"),
    ("prev_lancamento",       "real_lancamento",       "Lançamento"),
]


def calcular_proximos_marcos(df_f: pd.DataFrame, dias: int = 7) -> pd.DataFrame:
    """Retorna marcos com data prevista em [hoje, hoje+dias] e sem data realizada."""
    hoje   = datetime.today().date()
    limite = hoje + timedelta(days=dias)
    linhas: list[dict] = []
    for _, row in df_f.iterrows():
        for col_prev, col_real, label in _MARCOS_HOME:
            prev_d = _parse_data(row.get(col_prev))
            real_d = _parse_data(row.get(col_real))
            if prev_d is not None and real_d is None and hoje <= prev_d <= limite:
                linhas.append({
                    "Projeto":        row.get("nome_projeto", row.get("projeto")),
                    "Marco":          label,
                    "Data Prevista":  prev_d.strftime("%d/%m/%Y"),
                    "Dias Restantes": (prev_d - hoje).days,
                })
    if not linhas:
        return pd.DataFrame(columns=["Projeto", "Marco", "Data Prevista", "Dias Restantes"])
    return pd.DataFrame(linhas).sort_values("Dias Restantes").reset_index(drop=True)


def calcular_marcos_vencidos(df_f: pd.DataFrame) -> pd.DataFrame:
    """Retorna marcos com data prevista < hoje e sem data realizada."""
    hoje = datetime.today().date()
    linhas: list[dict] = []
    for _, row in df_f.iterrows():
        for col_prev, col_real, label in _MARCOS_HOME:
            prev_d = _parse_data(row.get(col_prev))
            real_d = _parse_data(row.get(col_real))
            if prev_d is not None and real_d is None and prev_d < hoje:
                linhas.append({
                    "Projeto":       row.get("nome_projeto", row.get("projeto")),
                    "Marco":         label,
                    "Data Prevista": prev_d.strftime("%d/%m/%Y"),
                    "Dias de Atraso": (hoje - prev_d).days,
                })
    if not linhas:
        return pd.DataFrame(columns=["Projeto", "Marco", "Data Prevista", "Dias de Atraso"])
    return pd.DataFrame(linhas).sort_values("Dias de Atraso", ascending=False).reset_index(drop=True)


def calcular_kpis_home(df_dashboard: pd.DataFrame, risco: pd.DataFrame) -> dict:
    """Retorna KPIs consolidados para a Home Executiva."""
    n_ativos = len(df_dashboard)

    if risco.empty:
        n_alto = n_medio = n_baixo = 0
        exposicao = atraso_medio = 0.0
    else:
        n_alto  = int((risco["nivel_risco"] == "alto").sum())
        n_medio = int((risco["nivel_risco"] == "medio").sum())
        n_baixo = int((risco["nivel_risco"] == "baixo").sum())
        mask_estouro = risco["pct_projetado"].notna() & (risco["pct_projetado"] > 100)
        if mask_estouro.any():
            exposicao = float(
                risco.loc[mask_estouro].apply(
                    lambda r: r["orcamento"] * (r["pct_projetado"] / 100 - 1), axis=1
                ).sum()
            )
        else:
            exposicao = 0.0
        atraso_medio = float(risco["dias_atraso_max"].mean())

    consumo_medio = 0.0
    if (
        not df_dashboard.empty
        and "orcamento" in df_dashboard.columns
        and "pct_orcamento" in df_dashboard.columns
    ):
        df_com_orc = df_dashboard[df_dashboard["orcamento"] > 0]
        if not df_com_orc.empty:
            consumo_medio = float(df_com_orc["pct_orcamento"].mean())

    return {
        "n_ativos":            n_ativos,
        "n_alto_risco":        n_alto,
        "n_medio_risco":       n_medio,
        "n_baixo_risco":       n_baixo,
        "exposicao_financeira": exposicao,
        "consumo_medio_pct":   consumo_medio,
        "atraso_medio_dias":   atraso_medio,
    }


# ─────────────────────────────────────────────
# Analytics Executivos — Benchmarking + Saúde
# ─────────────────────────────────────────────

def calcular_benchmarking_segmento(df_f: pd.DataFrame) -> pd.DataFrame:
    """Agrupa projetos por segmento, retorna métricas médias por segmento."""
    if df_f.empty or "segmento" not in df_f.columns:
        return pd.DataFrame(
            columns=["segmento", "n_projetos", "consumo_medio_pct", "custo_total", "horas_total"]
        )
    df_s = df_f[
        df_f["segmento"].notna()
        & (df_f["segmento"].astype(str).str.strip() != "")
    ].copy()
    if df_s.empty:
        return pd.DataFrame(
            columns=["segmento", "n_projetos", "consumo_medio_pct", "custo_total", "horas_total"]
        )
    return (
        df_s.groupby("segmento")
        .agg(
            n_projetos=("projeto", "count"),
            consumo_medio_pct=("pct_orcamento", "mean"),
            custo_total=("valor_total", "sum"),
            horas_total=("horas_total", "sum"),
        )
        .reset_index()
        .sort_values("custo_total", ascending=False)
    )


def calcular_indice_saude(
    pct_orcamento: float, dias_atraso_max: int, status: str = ""
) -> int:
    """Índice de saúde 0–100. Maior = mais saudável."""
    score = 100
    if pct_orcamento > 100:
        score -= 20
    elif pct_orcamento > 80:
        score -= 10
    if dias_atraso_max > 30:
        score -= 30
    elif dias_atraso_max > 0:
        score -= 15
    if str(status).strip() == "Stand by":
        score -= 10
    elif str(status).strip() == "Cancelado":
        score -= 20
    if 0 < pct_orcamento < 60:
        score += 10
    return max(0, min(100, score))


# ─────────────────────────────────────────────
# Saúde do Portfólio
# ─────────────────────────────────────────────

def calcular_saude_portfolio(df_f: pd.DataFrame, risco: pd.DataFrame) -> pd.DataFrame:
    """Índice de saúde (0–100) para cada projeto. Combina pct_projetado + dias_atraso do risco."""
    if df_f.empty:
        return pd.DataFrame(columns=["projeto", "nome_projeto", "saude", "classificacao"])
    base = df_f[["projeto", "nome_projeto"]].copy()
    base["status_projeto"] = df_f["status_projeto"].fillna("") if "status_projeto" in df_f.columns else ""
    if not risco.empty and "projeto" in risco.columns:
        cols_r = [c for c in ["projeto", "pct_projetado", "dias_atraso_max"] if c in risco.columns]
        base = base.merge(risco[cols_r].drop_duplicates("projeto"), on="projeto", how="left")
    if "pct_projetado"  not in base.columns: base["pct_projetado"]  = 0.0
    if "dias_atraso_max" not in base.columns: base["dias_atraso_max"] = 0
    base["pct_projetado"]   = base["pct_projetado"].fillna(0.0)
    base["dias_atraso_max"] = base["dias_atraso_max"].fillna(0).astype(int)
    base["saude"] = base.apply(
        lambda r: calcular_indice_saude(
            float(r["pct_projetado"]), int(r["dias_atraso_max"]), str(r["status_projeto"])
        ),
        axis=1,
    )
    base["classificacao"] = base["saude"].apply(
        lambda s: "🟢 Saudável" if s >= 80 else ("🟡 Atenção" if s >= 50 else "🔴 Crítico")
    )
    return base.sort_values("saude", ascending=False).reset_index(drop=True)


def calcular_burn_rate_tendencia(df_br: pd.DataFrame) -> dict:
    """
    Média dos últimos 3 meses de burn rate e delta vs 3 meses anteriores.
    Retorna {'media_3m': float, 'delta_pct': float|None, 'tendencia': '↑'|'↓'|'→'}
    """
    if df_br.empty or "mes_ref" not in df_br.columns or "custo_mensal" not in df_br.columns:
        return {"media_3m": 0.0, "delta_pct": None, "tendencia": "→"}
    por_mes  = df_br.groupby("mes_ref")["custo_mensal"].sum().sort_index()
    media_3m = float(por_mes.tail(3).mean())
    if len(por_mes) < 4:
        return {"media_3m": media_3m, "delta_pct": None, "tendencia": "→"}
    anteriores = por_mes.iloc[-6:-3] if len(por_mes) >= 6 else por_mes.iloc[:-3]
    if anteriores.empty:
        return {"media_3m": media_3m, "delta_pct": None, "tendencia": "→"}
    media_ant = float(anteriores.mean())
    if media_ant == 0:
        return {"media_3m": media_3m, "delta_pct": None, "tendencia": "→"}
    delta_pct = (media_3m - media_ant) / media_ant * 100
    tendencia = "↑" if delta_pct > 2 else ("↓" if delta_pct < -2 else "→")
    return {"media_3m": media_3m, "delta_pct": delta_pct, "tendencia": tendencia}
