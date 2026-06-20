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

from utils.db import (
    carregar_custos, carregar_horas, carregar_orcamentos,
    listar_importacoes, STATUS_OPCOES, STATUS_DEFAULT,
    salvar_custos, salvar_horas,
    salvar_orcamento, carregar_orcamento_projeto, salvar_previsao_periodo,
)
import re

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


def processar_arquivo_custos(arquivo) -> dict:
    """Lê, valida e salva um arquivo de custos.

    Retorna {"ok": bool, "mensagem": str, "colunas": list[str] | None}.
    `colunas` só é preenchido quando há erro de validação (uso em depuração na UI).
    """
    df = preparar_custos(ler_planilha_bytes(arquivo.read(), arquivo.name))
    erros = validar_colunas(df, COLUNAS_CUSTOS, "Custos")
    if erros:
        return {"ok": False, "mensagem": erros[0], "colunas": list(df.columns)}

    linhas, duplicado = salvar_custos(df, arquivo.name)
    if duplicado:
        return {"ok": False, "mensagem": f"'{arquivo.name}' já foi importado — ignorado.", "colunas": None}
    return {"ok": True, "mensagem": f"Custos: **{linhas} linhas** de `{arquivo.name}` salvas.", "colunas": None}


def processar_arquivo_horas(arquivo) -> dict:
    """Lê, valida e salva um arquivo de horas.

    Retorna {"ok": bool, "mensagem": str, "colunas": list[str] | None}.
    `colunas` só é preenchido quando há erro de validação (uso em depuração na UI).
    """
    df = preparar_horas(ler_planilha_bytes(arquivo.read(), arquivo.name))
    erros = validar_colunas(df, COLUNAS_HORAS, "Horas")
    if erros:
        return {"ok": False, "mensagem": erros[0], "colunas": list(df.columns)}

    linhas, duplicado = salvar_horas(df, arquivo.name)
    if duplicado:
        return {"ok": False, "mensagem": f"'{arquivo.name}' já foi importado — ignorado.", "colunas": None}
    return {"ok": True, "mensagem": f"Horas: **{linhas} linhas** de `{arquivo.name}` salvas.", "colunas": None}


def _texto_celula(valor) -> str:
    """Converte uma célula de planilha em string, tratando NaN/None como vazio."""
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def _numero_celula(valor) -> float:
    """Converte uma célula de planilha em float, tratando NaN/None/inválido como 0."""
    if pd.isna(valor):
        return 0.0
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def importar_orcamento_de_excel(conteudo: bytes) -> int:
    """Importa orçamentos e previsões a partir do conteúdo de um .xlsx exportado
    anteriormente (abas 'Orcamentos' e 'Previsoes'). Retorna o nº de projetos importados.
    """
    xl = pd.ExcelFile(io.BytesIO(conteudo))
    importados = 0

    if "Orcamentos" in xl.sheet_names:
        df_imp_orc = xl.parse("Orcamentos")
        for _, row in df_imp_orc.iterrows():
            proj = _texto_celula(row.get("projeto"))
            if not proj:
                continue

            # Status do Projeto: se a planilha importada não trouxer esta coluna
            # (ou vier vazia), preserva o status já salvo no banco em vez de
            # sobrescrever com vazio/Nulo.
            status_imp = _texto_celula(row.get("status_projeto"))
            if not status_imp or status_imp not in STATUS_OPCOES:
                existente = carregar_orcamento_projeto(proj)
                status_imp = (existente.get("status_projeto") if existente else None) or STATUS_DEFAULT

            salvar_orcamento(
                projeto               = proj,
                orcamento_previsto    = _numero_celula(row.get("orcamento_previsto")),
                status_projeto        = status_imp,
                data_inicio           = _texto_celula(row.get("data_inicio")) or None,
                prev_viabilidade      = _texto_celula(row.get("prev_viabilidade")) or None,
                prev_qualidade        = _texto_celula(row.get("prev_qualidade")) or None,
                prev_aprov_lancamento = _texto_celula(row.get("prev_aprov_lancamento")) or None,
                prev_lancamento       = _texto_celula(row.get("prev_lancamento")) or None,
                real_viabilidade      = _texto_celula(row.get("real_viabilidade")) or None,
                real_qualidade        = _texto_celula(row.get("real_qualidade")) or None,
                real_aprov_lancamento = _texto_celula(row.get("real_aprov_lancamento")) or None,
                real_lancamento       = _texto_celula(row.get("real_lancamento")) or None,
                nome_projeto_editado  = _texto_celula(row.get("nome_projeto_editado")) or None,
            )
            importados += 1

    if "Previsoes" in xl.sheet_names:
        df_imp_prev = xl.parse("Previsoes")
        for _, row in df_imp_prev.iterrows():
            proj = _texto_celula(row.get("projeto"))
            if not proj:
                continue
            salvar_previsao_periodo(
                projeto      = proj,
                periodo      = _texto_celula(row.get("periodo")),
                valor        = _numero_celula(row.get("valor")),
                tipo_periodo = _texto_celula(row.get("tipo_periodo")) or "anual",
                descricao    = _texto_celula(row.get("descricao")) or None,
            )

    return importados


def aplicar_filtros(
    df: pd.DataFrame,
    df_custos_raw: pd.DataFrame,
    projetos_sel: list,
    anos_sel: list,
    meses_sel: list,
    status_sel: list,
) -> pd.DataFrame:
    """Aplica os 4 critérios de filtro (Projetos, Ano, Mês, Status).
    Seleção vazia em qualquer critério = não filtra por ele (mostra tudo).
    """
    df_f = df.copy()
    if projetos_sel:
        df_f = df_f[df_f["nome_projeto"].isin(projetos_sel)]
    if anos_sel and "ano" in df_custos_raw.columns:
        cc_anos = df_custos_raw[df_custos_raw["ano"].astype(str).isin(anos_sel)]["centro_de_custo"].unique()
        df_f = df_f[df_f["projeto"].isin(cc_anos)]
    if meses_sel and "mes" in df_custos_raw.columns:
        cc_meses = df_custos_raw[df_custos_raw["mes"].astype(str).isin(meses_sel)]["centro_de_custo"].unique()
        df_f = df_f[df_f["projeto"].isin(cc_meses)]
    if status_sel and "status_projeto" in df_f.columns:
        df_f = df_f[df_f["status_projeto"].isin(status_sel)]
    return df_f


def _limpar_filtros_callback() -> None:
    """Callback do botão 'Limpar filtros'. Precisa rodar via on_click (antes do
    rerun recriar os widgets) — atribuir a st.session_state[key] depois que o
    widget com aquele key já foi instanciado no mesmo run lança
    StreamlitAPIException.
    """
    st.session_state["filtro_projetos"] = []
    st.session_state["filtro_anos"]     = []
    st.session_state["filtro_meses"]    = []
    st.session_state["filtro_status"]   = []


def render_filtros_sidebar(df: pd.DataFrame, df_custos_raw: pd.DataFrame) -> pd.DataFrame:
    """Renderiza os 4 filtros (Projetos, Ano, Mês, Status) na sidebar e
    retorna o df já filtrado. Usa st.session_state para persistir as
    escolhas entre as páginas Dashboard e Andamento dos Projetos (mesmas
    chaves). Seleção vazia em qualquer filtro = sem filtro (mostra tudo).
    """
    lista_projetos = sorted(df["nome_projeto"].dropna().unique().tolist())
    lista_anos     = sorted(df_custos_raw["ano"].dropna().astype(str).unique().tolist()) if "ano" in df_custos_raw.columns else []
    lista_meses    = sorted(df_custos_raw["mes"].dropna().astype(str).unique().tolist()) if "mes" in df_custos_raw.columns else []
    lista_status   = sorted(df["status_projeto"].dropna().unique().tolist()) if "status_projeto" in df.columns else []

    if "filtro_projetos" not in st.session_state: st.session_state["filtro_projetos"] = []
    if "filtro_anos"     not in st.session_state: st.session_state["filtro_anos"]     = anos_default(lista_anos)
    if "filtro_meses"    not in st.session_state: st.session_state["filtro_meses"]    = []
    if "filtro_status"   not in st.session_state: st.session_state["filtro_status"]   = status_ativos(lista_status)

    st.session_state["filtro_projetos"] = [p for p in st.session_state["filtro_projetos"] if p in lista_projetos]
    st.session_state["filtro_anos"]     = [a for a in st.session_state["filtro_anos"]     if a in lista_anos]
    st.session_state["filtro_meses"]    = [m for m in st.session_state["filtro_meses"]    if m in lista_meses]
    st.session_state["filtro_status"]   = [s for s in st.session_state["filtro_status"]   if s in lista_status]

    with st.sidebar:
        st.header("🔍 Filtros")

        projetos_selecionados = st.multiselect("Projetos:", options=lista_projetos,
            default=st.session_state["filtro_projetos"], key="filtro_projetos")
        st.caption(f"{len(projetos_selecionados)} de {len(lista_projetos)} selecionados"
                   if projetos_selecionados else f"Mostrando todos os {len(lista_projetos)} projetos")

        anos_selecionados = st.multiselect("Ano:", options=lista_anos,
            default=st.session_state["filtro_anos"], key="filtro_anos")
        st.caption(f"{len(anos_selecionados)} de {len(lista_anos)} selecionados"
                   if anos_selecionados else f"Mostrando todos os {len(lista_anos)} anos")

        meses_selecionados = st.multiselect("Mês:", options=lista_meses,
            default=st.session_state["filtro_meses"], key="filtro_meses")
        st.caption(f"{len(meses_selecionados)} de {len(lista_meses)} selecionados"
                   if meses_selecionados else f"Mostrando todos os {len(lista_meses)} meses")

        status_selecionados = st.multiselect("Status do Projeto:", options=lista_status,
            default=st.session_state["filtro_status"], key="filtro_status")
        st.caption(f"{len(status_selecionados)} de {len(lista_status)} selecionados"
                   if status_selecionados else f"Mostrando todos os {len(lista_status)} status")

        st.button("🔄 Limpar filtros", use_container_width=True, on_click=_limpar_filtros_callback)

    return aplicar_filtros(
        df, df_custos_raw,
        projetos_selecionados, anos_selecionados, meses_selecionados, status_selecionados,
    )


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
        "projeto", "nome_projeto_editado", "orcamento_previsto", "status_projeto",
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
        merged["nome_projeto_editado"] = None
        merged["status_projeto"] = None
        for col in COLUNAS_ORC[4:]:  # colunas de data
            merged[col] = None

    # Status do projeto: preenche com o valor padrão quando ausente/vazio
    if "status_projeto" in merged.columns:
        merged["status_projeto"] = merged["status_projeto"].apply(
            lambda v: v if v and str(v).strip() not in ("0", "None", "nan", "") else STATUS_DEFAULT
        )
    else:
        merged["status_projeto"] = STATUS_DEFAULT

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

    # Se o usuário editou o nome do projeto, usa o nome editado
    if "nome_projeto_editado" in merged.columns:
        mask = merged["nome_projeto_editado"].notna() & (merged["nome_projeto_editado"].astype(str).str.strip() != "")
        merged.loc[mask, "nome_projeto"] = merged.loc[mask, "nome_projeto_editado"]

    # ── Corrigir mes_ref de horas: garante que jan/fev 2026 sejam parseados corretamente
    # O campo 'periodo' às vezes vem como número serial Excel (ex: 46023) — converte via origin
    if not df_horas.empty and "periodo" in df_horas.columns:
        def _parse_periodo_robusto(serie: pd.Series) -> pd.Series:
            # Tenta datetime normal primeiro
            parsed = pd.to_datetime(serie, dayfirst=True, errors="coerce")
            # Para valores ainda NaT, tenta interpretar como serial Excel (número)
            mask_nat = parsed.isna()
            if mask_nat.any():
                numericos = pd.to_numeric(serie[mask_nat], errors="coerce")
                mask_num = numericos.notna()
                if mask_num.any():
                    from datetime import datetime as _dt
                    # Excel serial: 1 = 1900-01-01
                    parsed[mask_nat & mask_num] = pd.to_datetime(
                        numericos[mask_num] - 25569, unit="D", origin="1970-01-01", errors="coerce"
                    )
            return parsed
        df_horas["mes_ref"] = _parse_periodo_robusto(df_horas["periodo"]).dt.to_period("M").astype(str)

    return merged, df_custos, df_horas


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def formata_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formata_brl_curto(valor: float) -> str:
    """
    Formato abreviado para cartões de KPI (Roadmap 1.3):
      1.540.000 -> "R$ 1,54 mi"
      356.000   -> "R$ 356,0 mil"
      -1.190.000 -> "-R$ 1,19 mi"
    Mantém o valor cheio acessível via tooltip nas chamadas.
    """
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "R$ 0,00"

    sinal = "-" if v < 0 else ""
    a = abs(v)

    if a >= 1_000_000_000:
        num = f"{a/1_000_000_000:.2f} bi"
    elif a >= 1_000_000:
        num = f"{a/1_000_000:.2f} mi"
    elif a >= 1_000:
        num = f"{a/1_000:.1f} mil"
    else:
        # valores pequenos: mostra cheio, sem abreviar
        return formata_brl(v)

    num = num.replace(".", ",")
    return f"{sinal}R$ {num}"


# ─────────────────────────────────────────────
# Selo de atualização e completude (Roadmap 1.1)
# ─────────────────────────────────────────────

def info_atualizacao(df_dashboard: pd.DataFrame) -> dict:
    """
    Retorna metadados para o selo de confiança exibido no topo das
    páginas de análise:
      - ultima_importacao (str dd/mm/aaaa HH:MM ou None)
      - tipo_ultima       (custos / horas / None)
      - n_total           (projetos no df)
      - n_com_orcamento   (projetos com orçamento > 0)
    """
    info = {
        "ultima_importacao": None,
        "tipo_ultima": None,
        "n_total": 0,
        "n_com_orcamento": 0,
    }

    # Data da última importação (qualquer tipo)
    try:
        imp = listar_importacoes()
        if not imp.empty:
            topo = imp.iloc[0]
            bruto = str(topo.get("importado_em", "")).strip()
            try:
                dt = datetime.strptime(bruto[:19], "%Y-%m-%d %H:%M:%S")
                info["ultima_importacao"] = dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                info["ultima_importacao"] = bruto or None
            info["tipo_ultima"] = str(topo.get("tipo", "")) or None
    except Exception:
        pass

    # Completude de orçamento
    if df_dashboard is not None and not df_dashboard.empty:
        info["n_total"] = len(df_dashboard)
        if "orcamento" in df_dashboard.columns:
            info["n_com_orcamento"] = int((df_dashboard["orcamento"] > 0).sum())

    return info


def render_selo_dados(df_dashboard: pd.DataFrame) -> None:
    """
    Renderiza, via st.caption, um selo discreto com a data da última
    importação e a completude de orçamento. Deve ser chamado logo
    abaixo do título nas páginas de análise.
    """
    import streamlit as _st
    info = info_atualizacao(df_dashboard)

    partes = []
    if info["ultima_importacao"]:
        rotulo_tipo = {"custos": "custos", "horas": "horas"}.get(info["tipo_ultima"], "dados")
        partes.append(f"🔄 Dados atualizados em **{info['ultima_importacao']}** (último envio: {rotulo_tipo})")
    else:
        partes.append("🔄 Nenhuma importação registrada ainda")

    if info["n_total"] > 0:
        n_ok  = info["n_com_orcamento"]
        n_tot = info["n_total"]
        falta = n_tot - n_ok
        if falta > 0:
            partes.append(f"🎯 **{n_ok} de {n_tot}** projetos com orçamento cadastrado · {falta} sem orçamento")
        else:
            partes.append(f"🎯 Todos os {n_tot} projetos com orçamento cadastrado")

    _st.caption("  ·  ".join(partes))


def aviso_truncamento(n_total: int, limite: int | None = None) -> None:
    """
    Exibe um aviso discreto quando um gráfico mostra apenas parte dos
    projetos (Roadmap 1.2). Deve ser chamado logo após o st.plotly_chart
    do gráfico que aplica o corte.
    """
    import streamlit as _st
    from utils.charts import LIMITE_GRAFICO
    limite = limite or LIMITE_GRAFICO
    if n_total > limite:
        _st.caption(
            f"ℹ️ Exibindo os **{limite}** principais de **{n_total}** projetos. "
            f"Ajuste os filtros na barra lateral para ver outros."
        )


# ─────────────────────────────────────────────
# Gestão por exceção (Roadmap 2.1 e 2.2)
# ─────────────────────────────────────────────

def detectar_excecoes(df: pd.DataFrame) -> dict:
    """
    Analisa o df (já filtrado) e identifica os projetos que exigem atenção.
    Retorna um dicionário com listas de nomes de projeto por categoria, além
    de métricas agregadas usadas no KPI de Saldo.

    Categorias:
      - estouro      : realizado > orçamento (orçamento cadastrado)
      - atrasados    : lançamento previsto já passou e não foi realizado,
                       OU realizado depois do previsto
      - stand_by     : status_projeto == "Stand by"
      - cancelados   : status_projeto == "Cancelado"
      - sem_orcamento: projetos sem orçamento cadastrado

    Métricas:
      - n_estouro, excedente_total (R$ somado acima do orçamento)
    """
    from datetime import datetime as _dt
    hoje = _dt.today().date()

    resultado = {
        "estouro": [],
        "atrasados": [],
        "stand_by": [],
        "cancelados": [],
        "sem_orcamento": [],
        "n_estouro": 0,
        "excedente_total": 0.0,
    }
    if df is None or df.empty:
        return resultado

    def _parse(val):
        if not val or str(val) in ("0", "None", "nan", ""):
            return None
        try:
            return _dt.strptime(str(val)[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    for _, row in df.iterrows():
        nome = row.get("nome_projeto", row.get("projeto", "—"))
        orc  = row.get("orcamento", 0) or 0
        val  = row.get("valor_total", 0) or 0

        # Estouro de orçamento
        if orc > 0 and val > orc:
            resultado["estouro"].append(nome)
            resultado["n_estouro"] += 1
            resultado["excedente_total"] += (val - orc)

        # Sem orçamento cadastrado
        if not orc or orc <= 0:
            resultado["sem_orcamento"].append(nome)

        # Atraso de lançamento
        prev_d = _parse(row.get("prev_lancamento"))
        real_d = _parse(row.get("real_lancamento"))
        if prev_d:
            ref = real_d if real_d else hoje
            if ref > prev_d:
                resultado["atrasados"].append(nome)

        # Status
        status = str(row.get("status_projeto", "")).strip()
        if status == "Stand by":
            resultado["stand_by"].append(nome)
        elif status == "Cancelado":
            resultado["cancelados"].append(nome)

    return resultado


def render_faixa_alertas(df: pd.DataFrame) -> None:
    """
    Faixa de alertas no topo do Resumo Geral (Roadmap 2.1).
    Mostra contagens das exceções mais relevantes. Quando não há
    exceções, exibe uma mensagem positiva discreta.
    """
    import streamlit as _st
    exc = detectar_excecoes(df)

    cartoes = []
    if exc["estouro"]:
        cartoes.append(("🚨", len(exc["estouro"]), "acima do orçamento", "#dc2626"))
    if exc["atrasados"]:
        cartoes.append(("⏰", len(exc["atrasados"]), "com lançamento atrasado", "#f59e0b"))
    if exc["stand_by"]:
        cartoes.append(("⏸️", len(exc["stand_by"]), "em Stand by", "#a78bfa"))
    if exc["cancelados"]:
        cartoes.append(("✖️", len(exc["cancelados"]), "cancelados", "#94a3b8"))

    if not cartoes:
        _st.success("✅ Nenhuma exceção detectada nos projetos filtrados — tudo dentro do previsto.")
        return

    # Renderiza cartões lado a lado
    cols = _st.columns(len(cartoes))
    for col, (icone, n, rotulo, cor) in zip(cols, cartoes):
        col.markdown(f"""
        <div style="border:1px solid {cor}55;background:{cor}15;border-radius:10px;
                    padding:12px 14px;text-align:center">
            <div style="font-size:22px;font-weight:800;color:{cor}">{icone} {n}</div>
            <div style="font-size:12px;opacity:.8;margin-top:2px">{rotulo}</div>
        </div>""", unsafe_allow_html=True)

    # Detalhe expansível com os nomes dos projetos de cada categoria
    with _st.expander("Ver projetos que exigem atenção"):
        if exc["estouro"]:
            _st.markdown("**🚨 Acima do orçamento:** " + ", ".join(exc["estouro"]))
        if exc["atrasados"]:
            _st.markdown("**⏰ Lançamento atrasado:** " + ", ".join(exc["atrasados"]))
        if exc["stand_by"]:
            _st.markdown("**⏸️ Em Stand by:** " + ", ".join(exc["stand_by"]))
        if exc["cancelados"]:
            _st.markdown("**✖️ Cancelados:** " + ", ".join(exc["cancelados"]))


def cor_status(pct: float) -> str:
    if pct > 100:
        return "🚨"
    if pct >= 90:
        return "🟡"
    return "🟢"


# ─────────────────────────────────────────────
# Status do Projeto — cores para badges
# ─────────────────────────────────────────────

CORES_STATUS_PROJETO = {
    "CC criado":                          ("rgba(148,163,184,.2)", "#cbd5e1"),
    "Viabilizado":                        ("rgba(56,189,248,.2)",  "#7dd3fc"),
    "Aprovado em Critérios de Qualidade": ("rgba(99,102,241,.2)",  "#a5b4fc"),
    "Aprovado para Lançamento":           ("rgba(168,85,247,.2)",  "#d8b4fe"),
    "Lançado":                            ("rgba(34,197,94,.2)",   "#86efac"),
    "Stand by":                           ("rgba(234,179,8,.2)",   "#fde047"),
    "Cancelado":                          ("rgba(220,38,38,.2)",   "#fca5a5"),
}


def cor_status_projeto(status: str) -> tuple[str, str]:
    """Retorna (cor_fundo, cor_texto) para o badge de status do projeto."""
    return CORES_STATUS_PROJETO.get(status, CORES_STATUS_PROJETO[STATUS_DEFAULT])


def badge_status_projeto(status: str) -> str:
    """HTML de um badge colorido para o status do projeto."""
    bg, fg = cor_status_projeto(status)
    return (
        f"<span style='background:{bg};color:{fg};font-size:12px;font-weight:700;"
        f"border-radius:20px;padding:3px 12px;white-space:nowrap'>{status}</span>"
    )


# ─────────────────────────────────────────────
# Agrupamento por Nome do Projeto (ignora CC)
# ─────────────────────────────────────────────

_RE_CC_PREFIXO = re.compile(r"^\d{9}\s+(.*)$")


def limpar_nome_projeto(nome) -> str:
    """
    Remove o prefixo de 9 dígitos (Centro de Custo) + espaço do início
    do nome do projeto, se presente.
    Ex: "100150268 Nome do Projeto" -> "Nome do Projeto"
    """
    nome = str(nome).strip()
    m = _RE_CC_PREFIXO.match(nome)
    if m:
        return m.group(1).strip()
    return nome


def agrupar_por_nome_projeto(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa as linhas de df (já agregadas por CC) pelo nome do projeto
    "limpo" (sem o prefixo de 9 dígitos do CC). Projetos diferentes que
    compartilham o mesmo nome após a limpeza são consolidados em uma
    única linha, somando métricas numéricas e combinando os CCs.

    Usado na aba Detalhamento de "Andamento dos Projetos".
    """
    if df.empty:
        return df.copy()

    df = df.copy()
    df["_nome_limpo"] = df["nome_projeto"].apply(limpar_nome_projeto)

    colunas_soma = [
        "valor_total", "horas_total", "orcamento", "orcamento_previsto",
        "n_colaboradores",
    ]
    colunas_soma = [c for c in colunas_soma if c in df.columns]

    def _primeiro_valido(serie: pd.Series):
        for v in serie:
            if v is not None and str(v).strip() not in ("", "0", "None", "nan"):
                return v
        return serie.iloc[0] if len(serie) else None

    outras_colunas = [
        c for c in df.columns
        if c not in colunas_soma
        and c not in ("_nome_limpo", "nome_projeto", "projeto",
                       "custo_por_hora", "pct_orcamento", "saldo_orcamento")
    ]

    agg_dict = {c: "sum" for c in colunas_soma}
    for c in outras_colunas:
        agg_dict[c] = _primeiro_valido

    grupos = df.groupby("_nome_limpo").agg(agg_dict).reset_index()

    # Lista de CCs originais agrupados nesta linha
    ccs_por_grupo = (
        df.groupby("_nome_limpo")["projeto"]
        .apply(lambda s: sorted(set(s.astype(str))))
        .reset_index(name="_ccs")
    )
    grupos = grupos.merge(ccs_por_grupo, on="_nome_limpo")

    grupos.rename(columns={"_nome_limpo": "nome_projeto"}, inplace=True)
    grupos["projeto"] = grupos["_ccs"].apply(lambda lst: ", ".join(lst))

    # Recalcula métricas derivadas após a soma
    for col, default in [("valor_total", 0), ("horas_total", 0), ("orcamento", 0)]:
        if col not in grupos.columns:
            grupos[col] = default

    grupos["custo_por_hora"] = grupos.apply(
        lambda r: r["valor_total"] / r["horas_total"] if r["horas_total"] > 0 else 0, axis=1
    )
    grupos["pct_orcamento"] = grupos.apply(
        lambda r: r["valor_total"] / r["orcamento"] * 100 if r["orcamento"] > 0 else 0, axis=1
    )
    grupos["saldo_orcamento"] = grupos["orcamento"] - grupos["valor_total"]

    return grupos


# ─────────────────────────────────────────────
# Projeção de custo na conclusão — burn rate (Roadmap 3.2)
# ─────────────────────────────────────────────

def projecao_burn_rate(row, df_custos_proj: pd.DataFrame) -> dict:
    """
    Estima o custo final de um projeto pelo RITMO MÉDIO MENSAL de gasto.

    Método (ritmo médio mensal):
      ritmo = total_realizado / nº de meses com lançamento de custo
      meses_restantes = meses entre o mês atual e o mês de lançamento previsto
      projecao_final = total_realizado + (ritmo * meses_restantes)

    Retorna dict com:
      - realizado          : custo já gasto
      - ritmo_mensal       : média mensal de gasto
      - meses_decorridos   : nº de meses com gasto
      - meses_restantes    : meses até o lançamento previsto (0 se já passou/sem data)
      - projecao_final     : custo estimado na conclusão
      - orcamento          : orçamento previsto (0 se não houver)
      - pct_projetado      : projecao_final / orcamento * 100 (None se sem orçamento)
      - vai_estourar       : True se projecao_final > orcamento
      - status             : 'sem_dados' | 'concluido' | 'projetado'
    """
    from datetime import datetime as _dt

    realizado = float(row.get("valor_total", 0) or 0)
    orcamento = float(row.get("orcamento", 0) or 0)

    base = {
        "realizado": realizado,
        "ritmo_mensal": 0.0,
        "meses_decorridos": 0,
        "meses_restantes": 0,
        "projecao_final": realizado,
        "orcamento": orcamento,
        "pct_projetado": (realizado / orcamento * 100) if orcamento > 0 else None,
        "vai_estourar": (realizado > orcamento) if orcamento > 0 else False,
        "status": "sem_dados",
    }

    if df_custos_proj is None or df_custos_proj.empty or "mes_ref" not in df_custos_proj.columns:
        return base

    val_col = "realizado" if "realizado" in df_custos_proj.columns else "valor"
    if val_col not in df_custos_proj.columns:
        return base

    # Meses distintos com gasto
    gasto_mes = (df_custos_proj.groupby("mes_ref")[val_col].sum()
                 .reset_index().sort_values("mes_ref"))
    gasto_mes = gasto_mes[gasto_mes[val_col] != 0]
    n_meses = len(gasto_mes)
    if n_meses == 0:
        return base

    ritmo = realizado / n_meses
    base["ritmo_mensal"] = ritmo
    base["meses_decorridos"] = n_meses

    # Meses restantes até o lançamento previsto
    def _parse(val):
        if not val or str(val) in ("0", "None", "nan", ""):
            return None
        try:
            return _dt.strptime(str(val)[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    prev_lanc = _parse(row.get("prev_lancamento"))
    real_lanc = _parse(row.get("real_lancamento"))
    hoje = _dt.today().date()

    # Projeto já lançado → custo final é o próprio realizado
    if real_lanc is not None:
        base["projecao_final"] = realizado
        base["status"] = "concluido"
        base["pct_projetado"] = (realizado / orcamento * 100) if orcamento > 0 else None
        base["vai_estourar"] = (realizado > orcamento) if orcamento > 0 else False
        return base

    meses_restantes = 0
    if prev_lanc is not None and prev_lanc > hoje:
        meses_restantes = (prev_lanc.year - hoje.year) * 12 + (prev_lanc.month - hoje.month)
        meses_restantes = max(meses_restantes, 0)

    base["meses_restantes"] = meses_restantes
    base["projecao_final"]  = realizado + ritmo * meses_restantes
    base["status"] = "projetado"

    if orcamento > 0:
        base["pct_projetado"] = base["projecao_final"] / orcamento * 100
        base["vai_estourar"]  = base["projecao_final"] > orcamento

    return base


MARCOS_RISCO = [
    ("prev_viabilidade", "real_viabilidade", "Viabilidade"),
    ("prev_qualidade", "real_qualidade", "Qualidade"),
    ("prev_aprov_lancamento", "real_aprov_lancamento", "Aprovação para Lançamento"),
    ("prev_lancamento", "real_lancamento", "Lançamento"),
]


def _parse_data_marco(val):
    from datetime import datetime as _dt
    if not val or str(val) in ("0", "None", "nan", ""):
        return None
    try:
        return _dt.strptime(str(val)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def calcular_risco_portfolio(df: pd.DataFrame, df_custos_raw: pd.DataFrame) -> pd.DataFrame:
    """Classifica cada projeto em nivel_risco ('alto'/'medio'/'baixo'), combinando
    a projeção de custo (projecao_burn_rate) com atraso em qualquer marco do
    cronograma. Retorna um DataFrame ordenado por risco (alto primeiro).
    """
    from datetime import datetime as _dt

    colunas = [
        "projeto", "nome_projeto", "nivel_risco", "motivos", "pct_projetado",
        "dias_atraso_max", "orcamento", "realizado", "proxima_fase", "proxima_fase_data",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=colunas)

    hoje = _dt.today().date()
    linhas = []

    for _, row in df.iterrows():
        projeto = row.get("projeto")
        nome_projeto = row.get("nome_projeto", projeto)
        orcamento = row.get("orcamento", 0) or 0
        motivos = []

        if df_custos_raw is not None and not df_custos_raw.empty and "centro_de_custo" in df_custos_raw.columns:
            df_c_proj = df_custos_raw[df_custos_raw["centro_de_custo"] == projeto]
        else:
            df_c_proj = pd.DataFrame()
        proj_burn = projecao_burn_rate(row, df_c_proj)
        pct = proj_burn["pct_projetado"]
        realizado = proj_burn["realizado"]

        if pct is None:
            risco_custo = "indeterminado"
            motivos.append("Sem orçamento cadastrado")
        elif pct > 100:
            risco_custo = "alto"
            motivos.append(f"Projeção de custo: {pct:.0f}% do orçamento")
        elif pct >= 80:
            risco_custo = "medio"
            motivos.append(f"Projeção de custo: {pct:.0f}% do orçamento")
        else:
            risco_custo = "baixo"

        dias_atraso_max = 0
        proxima_fase = None
        proxima_fase_data = None
        for col_prev, col_real, label in MARCOS_RISCO:
            prev_d = _parse_data_marco(row.get(col_prev))
            real_d = _parse_data_marco(row.get(col_real))
            if proxima_fase is None and real_d is None and prev_d is not None:
                proxima_fase = label
                proxima_fase_data = prev_d
            if prev_d is None:
                continue
            ref = real_d if real_d else hoje
            if ref > prev_d:
                dias = (ref - prev_d).days
                motivos.append(f"{label} atrasado(a) {dias} dia(s)")
                dias_atraso_max = max(dias_atraso_max, dias)

        if risco_custo == "alto" or dias_atraso_max > 0:
            nivel_risco = "alto"
        elif risco_custo == "medio":
            nivel_risco = "medio"
        else:
            nivel_risco = "baixo"

        linhas.append({
            "projeto": projeto,
            "nome_projeto": nome_projeto,
            "nivel_risco": nivel_risco,
            "motivos": motivos,
            "pct_projetado": pct,
            "dias_atraso_max": dias_atraso_max,
            "orcamento": orcamento,
            "realizado": realizado,
            "proxima_fase": proxima_fase,
            "proxima_fase_data": proxima_fase_data,
        })

    resultado = pd.DataFrame(linhas, columns=colunas)
    ordem = {"alto": 0, "medio": 1, "baixo": 2}
    resultado["_ordem"] = resultado["nivel_risco"].map(ordem)
    resultado = resultado.sort_values(
        ["_ordem", "pct_projetado"], ascending=[True, False], na_position="last"
    ).drop(columns="_ordem").reset_index(drop=True)
    return resultado


# ─────────────────────────────────────────────
# Defaults de filtros curados (Roadmap 4.2)
# ─────────────────────────────────────────────

# "Projeto ativo" = qualquer status exceto os terminais abaixo.
STATUS_TERMINAIS = {"Cancelado", "Lançado"}


def status_ativos(lista_status: list) -> list:
    """
    A partir da lista de status disponíveis, retorna apenas os 'ativos'
    (exclui Cancelado e Lançado). Usado como default do filtro de status.
    Se a exclusão esvaziar tudo, devolve a lista original (evita tela vazia).
    """
    ativos = [s for s in lista_status if s not in STATUS_TERMINAIS]
    return ativos if ativos else list(lista_status)


def ano_corrente_str() -> str:
    """Retorna o ano atual como string (ex: '2026'), para default do filtro de ano."""
    from datetime import datetime as _dt
    return str(_dt.today().year)


def anos_default(lista_anos: list) -> list:
    """
    Default do filtro de ano: apenas o ano corrente, se existir na lista.
    Caso o ano corrente não esteja disponível, devolve todos (fallback seguro).
    """
    atual = ano_corrente_str()
    if atual in [str(a) for a in lista_anos]:
        return [a for a in lista_anos if str(a) == atual]
    return list(lista_anos)


# ─────────────────────────────────────────────
# Rótulo textual de consumo (Roadmap 5.1 — acessibilidade)
# ─────────────────────────────────────────────

def rotulo_consumo(pct: float) -> str:
    """
    Rótulo textual da faixa de consumo de orçamento, independente de cor
    (acessível para daltônicos). Faixas:
      > 100  -> "Estouro"
      >= 80  -> "Atenção"
      < 80   -> "Saudável"
    """
    try:
        p = float(pct)
    except (TypeError, ValueError):
        return ""
    if p > 100:
        return "Estouro"
    if p >= 80:
        return "Atenção"
    return "Saudável"
