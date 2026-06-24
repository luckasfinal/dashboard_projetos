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
