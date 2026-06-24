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
