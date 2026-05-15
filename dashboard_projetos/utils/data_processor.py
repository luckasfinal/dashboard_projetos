"""
data_processor.py — lógica de transformação e agregação
Lê sempre do banco SQLite (histórico completo acumulado).

Mapeamento de colunas originais → nomes internos normalizados:

CUSTOS
  Data                             → data
  Ano                              → ano
  Mês                              → mes
  Filial                           → filial
  Área                             → area
  Centro de Custo                  → centro_de_custo   ← chave de projeto
  Conta                            → conta
  Cód. Parceiro Negócio            → cod_parceiro_negocio
  Parceiro Negócio                 → parceiro_negocio
  Histórico                        → historico
  Realizado                        → realizado          ← valor monetário

HORAS
  Período                          → periodo
  C.Custo                          → c_custo            ← chave de projeto
  Ordem Interna                    → ordem_interna
  Descrição Ordem Interna          → descricao_ordem_interna
  Centro de Lucro                  → centro_de_lucro
  Descrição C.Lucro                → descricao_c_lucro
  Matricula                        → matricula
  Nome                             → nome               ← colaborador
  CC Origem                        → cc_origem
  Descrição CC Origem              → descricao_cc_origem
  Hs Nor                           → hs_nor             ← horas normais
  Tipo de Projeto                  → tipo_de_projeto
  Cód Produto                      → cod_produto
  Descrição Produto                → descricao_produto
  CATEGORIA                        → categoria
  ATIVIDADE                        → atividade
  DETALHES                         → detalhes
  C.Custo - Descrição Ordem Interna→ c_custo_descricao_ordem_interna
  Matricula - Nome                 → matricula_nome
  Segmento                         → segmento
"""
import io
import unicodedata
import pandas as pd
import streamlit as st

from utils.db import carregar_custos, carregar_horas

# ─────────────────────────────────────────────
# Mapeamento: cabeçalho original → nome interno
# ─────────────────────────────────────────────

MAP_CUSTOS = {
    "data":                    "data",
    "ano":                     "ano",
    "mês":                     "mes",
    "mes":                     "mes",
    "filial":                  "filial",
    "área":                    "area",
    "area":                    "area",
    "centro de custo":         "centro_de_custo",
    "conta":                   "conta",
    "cód. parceiro negócio":   "cod_parceiro_negocio",
    "cod. parceiro negocio":   "cod_parceiro_negocio",
    "cód parceiro negócio":    "cod_parceiro_negocio",
    "parceiro negócio":        "parceiro_negocio",
    "parceiro negocio":        "parceiro_negocio",
    "histórico":               "historico",
    "historico":               "historico",
    "realizado":               "realizado",
}

MAP_HORAS = {
    "período":                              "periodo",
    "periodo":                              "periodo",
    "c.custo":                              "c_custo",
    "ordem interna":                        "ordem_interna",
    "descrição ordem interna":              "descricao_ordem_interna",
    "descricao ordem interna":              "descricao_ordem_interna",
    "centro de lucro":                      "centro_de_lucro",
    "descrição c.lucro":                    "descricao_c_lucro",
    "descricao c.lucro":                    "descricao_c_lucro",
    "matricula":                            "matricula",
    "matrícula":                            "matricula",
    "nome":                                 "nome",
    "cc origem":                            "cc_origem",
    "descrição cc origem":                  "descricao_cc_origem",
    "descricao cc origem":                  "descricao_cc_origem",
    "hs nor":                               "hs_nor",
    "tipo de projeto":                      "tipo_de_projeto",
    "cód produto":                          "cod_produto",
    "cod produto":                          "cod_produto",
    "descrição produto":                    "descricao_produto",
    "descricao produto":                    "descricao_produto",
    "categoria":                            "categoria",
    "atividade":                            "atividade",
    "detalhes":                             "detalhes",
    "c.custo - descrição ordem interna":    "c_custo_descricao_ordem_interna",
    "c.custo - descricao ordem interna":    "c_custo_descricao_ordem_interna",
    "matricula - nome":                     "matricula_nome",
    "matrícula - nome":                     "matricula_nome",
    "segmento":                             "segmento",
}

# Colunas obrigatórias para validação
COLUNAS_CUSTOS = {
    "centro_de_custo": str,
    "realizado":       float,
    "mes":             str,
    "ano":             str,
}

COLUNAS_HORAS = {
    "c_custo":  str,
    "hs_nor":   float,
    "nome":     str,
    "periodo":  str,
}


# ─────────────────────────────────────────────
# Helpers de leitura e normalização
# ─────────────────────────────────────────────

def _remover_acentos(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _normalizar_header(col) -> str:
    """Remove acentos, caixa baixa, strip — para comparação com o mapa."""
    return _remover_acentos(str(col).strip().lower())


def ler_planilha_bytes(conteudo: bytes, nome: str) -> pd.DataFrame:
    """Lê o arquivo e força os nomes de colunas para string (evita datetime em headers)."""
    if nome.lower().endswith(".csv"):
        df = pd.read_csv(io.BytesIO(conteudo), sep=None, engine="python")
    else:
        df = pd.read_excel(io.BytesIO(conteudo))
    # Garante que TODOS os nomes de colunas são string pura
    df.columns = [str(c) for c in df.columns]
    return df


def _aplicar_mapa(df: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    """Renomeia colunas do df usando o mapa {header_original_normalizado: nome_interno}."""
    rename = {}
    for col in df.columns:
        chave = _normalizar_header(col)
        if chave in mapa:
            rename[col] = mapa[chave]
    return df.rename(columns=rename)


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Fallback: snake_case simples para colunas que não estão no mapa."""
    df = df.copy()
    df.columns = [
        _remover_acentos(c).strip().lower()
         .replace(" ", "_").replace(".", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def validar_colunas(df: pd.DataFrame, esperadas: dict, nome: str) -> list[str]:
    faltando = [c for c in esperadas if c not in df.columns]
    if faltando:
        return [f"**{nome}** — colunas ausentes após mapeamento: `{', '.join(faltando)}`"]
    return []


def preparar_custos(df: pd.DataFrame) -> pd.DataFrame:
    df = _aplicar_mapa(df, MAP_CUSTOS)
    # Fallback para colunas que não bateram no mapa
    df = normalizar_colunas(df)
    # Limpa separador de milhar e converte realizado
    if "realizado" in df.columns:
        df["realizado"] = (
            df["realizado"].astype(str)
            .str.replace(r"\.", "", regex=True)   # remove ponto de milhar
            .str.replace(",", ".", regex=False)    # vírgula → ponto decimal
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )
    if "centro_de_custo" in df.columns:
        df["centro_de_custo"] = df["centro_de_custo"].astype(str).str.strip()
    return df


def preparar_horas(df: pd.DataFrame) -> pd.DataFrame:
    df = _aplicar_mapa(df, MAP_HORAS)
    df = normalizar_colunas(df)
    if "hs_nor" in df.columns:
        df["hs_nor"] = (
            df["hs_nor"].astype(str)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )
    if "c_custo" in df.columns:
        df["c_custo"] = df["c_custo"].astype(str).str.strip()
    return df


# ─────────────────────────────────────────────
# Agregação completa (lê do banco)
# ─────────────────────────────────────────────

@st.cache_data(ttl=5, show_spinner="Carregando dados históricos…")
def agregar_tudo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Lê TODO o histórico do banco e retorna (df_merged, df_custos_raw, df_horas_raw).
    Chave de projeto: centro_de_custo (custos) ↔ c_custo (horas).
    """
    df_custos = carregar_custos()
    df_horas  = carregar_horas()

    if df_custos.empty and df_horas.empty:
        return pd.DataFrame(), df_custos, df_horas

    # ── Custos ────────────────────────────────────────────────────────────────
    if not df_custos.empty:
        df_custos["realizado"] = pd.to_numeric(df_custos["realizado"], errors="coerce").fillna(0)
        df_custos["centro_de_custo"] = df_custos["centro_de_custo"].astype(str).str.strip()

        # Coluna de mês para série temporal
        if "data" in df_custos.columns:
            df_custos["mes_ref"] = pd.to_datetime(
                df_custos["data"], dayfirst=True, errors="coerce"
            ).dt.to_period("M").astype(str)
        elif "mes" in df_custos.columns and "ano" in df_custos.columns:
            df_custos["mes_ref"] = df_custos["ano"].astype(str) + "-" + df_custos["mes"].astype(str)

        custos_agg = df_custos.groupby("centro_de_custo").agg(
            valor_total=("realizado", "sum"),
            filial=("filial", "last"),
            area=("area", "last"),
        ).reset_index().rename(columns={"centro_de_custo": "projeto"})
    else:
        custos_agg = pd.DataFrame(columns=["projeto", "valor_total", "filial", "area"])

    # ── Horas ─────────────────────────────────────────────────────────────────
    if not df_horas.empty:
        df_horas["hs_nor"]   = pd.to_numeric(df_horas["hs_nor"], errors="coerce").fillna(0)
        df_horas["c_custo"]  = df_horas["c_custo"].astype(str).str.strip()

        if "periodo" in df_horas.columns:
            df_horas["mes_ref"] = pd.to_datetime(
                df_horas["periodo"], dayfirst=True, errors="coerce"
            ).dt.to_period("M").astype(str)

        horas_agg = df_horas.groupby("c_custo").agg(
            horas_total=("hs_nor", "sum"),
            n_colaboradores=("nome", "nunique"),
            colaboradores=("nome", lambda x: ", ".join(x.dropna().unique())),
            tipo_projeto=("tipo_de_projeto", "last"),
            segmento=("segmento", "last"),
        ).reset_index().rename(columns={"c_custo": "projeto"})
    else:
        horas_agg = pd.DataFrame(columns=["projeto", "horas_total", "n_colaboradores", "colaboradores"])

    # ── Merge ─────────────────────────────────────────────────────────────────
    merged = custos_agg.merge(horas_agg, on="projeto", how="outer").fillna(0)

    # Sem orçamento explícito: coluna placeholder para não quebrar lógica downstream
    if "orcamento" not in merged.columns:
        merged["orcamento"] = 0.0

    merged["custo_por_hora"]  = merged.apply(
        lambda r: r["valor_total"] / r["horas_total"] if r["horas_total"] > 0 else 0, axis=1
    )
    merged["pct_orcamento"] = merged.apply(
        lambda r: r["valor_total"] / r["orcamento"] * 100 if r["orcamento"] > 0 else 0, axis=1
    )
    merged["saldo_orcamento"] = merged["orcamento"] - merged["valor_total"]

    return merged, df_custos, df_horas


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def formata_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cor_status(pct: float) -> str:
    if pct > 100:
        return "🚨"
    if pct >= 90:
        return "🔴"
    if pct >= 70:
        return "🟡"
    return "🟢"
