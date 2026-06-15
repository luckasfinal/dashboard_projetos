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
