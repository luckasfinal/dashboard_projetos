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
            "nome_projeto":  row.get("nome_projeto", proj),
            "custo_atual":   custo,
            "pct_concluido": pct,
            "eac":           eac,
            "orcamento":     orc,
            "desvio_eac_pct": desvio,
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
