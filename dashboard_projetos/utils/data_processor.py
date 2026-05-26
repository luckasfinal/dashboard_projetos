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

from utils.db import carregar_custos, carregar_horas, carregar_orcamentos

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
    "mes":              str,
    "ano":              str,
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

def _clean_string(s: str) -> str:
    """Remove caracteres invisíveis (como BOM), espaços nulos e formatações indesejadas."""
    s = s.replace("\ufeff", "").replace("\u200b", "").strip()
    return s


def _remover_acentos(s: str) -> str:
    s = _clean_string(s)
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _normalizar_header(col) -> str:
    """Remove acentos, caixa baixa, strip e caracteres invisíveis."""
    s = _clean_string(str(col)).lower()
    return _remover_acentos(s)


def ler_planilha_bytes(conteudo: bytes, nome: str) -> pd.DataFrame:
    """Lê o arquivo aplicando limpeza rígida de codificação e separadores."""
    if nome.lower().endswith(".csv"):
        texto = conteudo.decode("utf-8-sig", errors="ignore")
        df = pd.read_csv(io.StringIO(texto), sep=";", engine="python")
    else:
        df = pd.read_excel(io.BytesIO(conteudo))

    df.columns = [_clean_string(str(c)) for c in df.columns]
    return df


def _aplicar_mapa(df: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    """Renomeia colunas do df usando o mapa {header_original_normalizado: nome_interno}."""
    rename = {}
    for col in df.columns:
        chave = _normalizar_header(col)
        if chave in mapa:
            rename[col] = mapa[chave]
        else:
            nome_limpo = _remover_acentos(col).lower().replace(" ", "_").replace(".", "_").replace("-", "_")
            rename[col] = _clean_string(nome_limpo)
    return df.rename(columns=rename)


def preparar_custos(df: pd.DataFrame) -> pd.DataFrame:
    df = _aplicar_mapa(df, MAP_CUSTOS)

    if "realizado" in df.columns:
        df["realizado"] = (
            df["realizado"].astype(str)
            .str.replace(r"\.", "", regex=True)
            .str.replace(",", ".", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )
    if "centro_de_custo" in df.columns:
        df["centro_de_custo"] = df["centro_de_custo"].astype(str).str.strip().str[:9]
    return df


def preparar_horas(df: pd.DataFrame) -> pd.DataFrame:
    df = _aplicar_mapa(df, MAP_HORAS)

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


def validar_colunas(df: pd.DataFrame, esperadas: dict, nome: str) -> list[str]:
    colunas_df_limpas = [_clean_string(str(c)) for c in df.columns]
    faltando = [c for c in esperadas if _clean_string(c) not in colunas_df_limpas]
    if faltando:
        return [f"**{nome}** — colunas ausentes após mapeamento: `{', '.join(faltando)}`"]
    return []


# ─────────────────────────────────────────────
# Agregação completa (lê do banco)
# ─────────────────────────────────────────────

@st.cache_data(ttl=5, show_spinner="Carregando dados históricos…")
def agregar_tudo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Lê TODO o histórico do banco e retorna (df_merged, df_custos_raw, df_horas_raw).
    Chave de projeto: centro_de_custo (custos) ↔ c_custo (horas).
    O df_merged inclui orcamento_previsto e todas as datas de cronograma vindas
    da tabela orcamentos_cronograma.
    """
    df_custos = carregar_custos()
    df_horas  = carregar_horas()
    df_orc    = carregar_orcamentos()

    if df_custos.empty and df_horas.empty:
        return pd.DataFrame(), df_custos, df_horas

    # ── Custos ────────────────────────────────────────────────────────────────
    if not df_custos.empty:
        df_custos["realizado"] = pd.to_numeric(df_custos["realizado"], errors="coerce").fillna(0)
        df_custos["centro_de_custo"] = df_custos["centro_de_custo"].astype(str).str.strip().str[:9]

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
        df_horas["hs_nor"]  = pd.to_numeric(df_horas["hs_nor"], errors="coerce").fillna(0)
        df_horas["c_custo"] = df_horas["c_custo"].astype(str).str.strip().str[:9]

        if "ordem_interna" in df_horas.columns:
            df_horas["ordem_interna"] = df_horas["ordem_interna"].astype(str).str.strip().str[-5:]

        if "periodo" in df_horas.columns:
            df_horas["mes_ref"] = pd.to_datetime(
                df_horas["periodo"], dayfirst=True, errors="coerce"
            ).dt.to_period("M").astype(str)

        nome_col_projeto = None
        for col in ["descricao_ordem_interna", "c_custo_descricao_ordem_interna", "descricao_produto"]:
            if col in df_horas.columns:
                nome_col_projeto = col
                break

        if nome_col_projeto:
            horas_agg = df_horas.groupby("c_custo").agg(
                nome_projeto=(nome_col_projeto, "last"),
                horas_total=("hs_nor", "sum"),
                n_colaboradores=("nome", "nunique"),
                colaboradores=("nome", lambda x: ", ".join(x.dropna().unique())),
                tipo_projeto=("tipo_de_projeto", "last"),
                segmento=("segmento", "last"),
            ).reset_index().rename(columns={"c_custo": "projeto"})
        else:
            horas_agg = df_horas.groupby("c_custo").agg(
                horas_total=("hs_nor", "sum"),
                n_colaboradores=("nome", "nunique"),
                colaboradores=("nome", lambda x: ", ".join(x.dropna().unique())),
                tipo_projeto=("tipo_de_projeto", "last"),
                segmento=("segmento", "last"),
            ).reset_index().rename(columns={"c_custo": "projeto"})
            horas_agg["nome_projeto"] = "Não Identificado"
    else:
        horas_agg = pd.DataFrame(columns=["projeto", "nome_projeto", "horas_total", "n_colaboradores", "colaboradores"])

    # ── Merge custos + horas ──────────────────────────────────────────────────
    merged = custos_agg.merge(horas_agg, on="projeto", how="outer").fillna(0)

    # ── Merge com orçamentos/cronograma ───────────────────────────────────────
    COLUNAS_ORC = [
        "projeto", "orcamento_previsto",
        "data_inicio",
        "prev_viabilidade", "prev_qualidade", "prev_aprov_lancamento", "prev_lancamento",
        "real_viabilidade", "real_qualidade", "real_aprov_lancamento", "real_lancamento",
    ]
    if not df_orc.empty:
        df_orc_sel = df_orc.reindex(columns=COLUNAS_ORC)
        df_orc_sel["projeto"] = df_orc_sel["projeto"].astype(str).str.strip()
        merged = merged.merge(df_orc_sel, on="projeto", how="left")
        merged["orcamento_previsto"] = pd.to_numeric(merged["orcamento_previsto"], errors="coerce").fillna(0)
    else:
        merged["orcamento_previsto"] = 0.0
        for col in COLUNAS_ORC[2:]:  # colunas de data
            merged[col] = None

    # Compatibilidade: mantém 'orcamento' apontando para orcamento_previsto
    merged["orcamento"] = merged["orcamento_previsto"]

    merged["custo_por_hora"] = merged.apply(
        lambda r: r["valor_total"] / r["horas_total"] if r["horas_total"] > 0 else 0, axis=1
    )
    merged["pct_orcamento"] = merged.apply(
        lambda r: r["valor_total"] / r["orcamento"] * 100 if r["orcamento"] > 0 else 0, axis=1
    )
    merged["saldo_orcamento"] = merged["orcamento"] - merged["valor_total"]

    # Filtra apenas projetos com gasto > 0
    merged = merged[merged["valor_total"] > 0].reset_index(drop=True)

    if "nome_projeto" in merged.columns:
        merged["nome_projeto"] = merged["nome_projeto"].replace(0, "Descrição do projeto não disponível")

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
        return "🟡"
    return "🟢"
