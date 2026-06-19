import pandas as pd
from utils.data_processor import aplicar_filtros


def _df_exemplo():
    df = pd.DataFrame({
        "projeto": ["100150001", "100150002", "100150003"],
        "nome_projeto": ["100150001 Alpha", "100150002 Beta", "100150003 Gama"],
        "status_projeto": ["Viabilizado", "Lançado", "Cancelado"],
    })
    df_custos_raw = pd.DataFrame({
        "centro_de_custo": ["100150001", "100150001", "100150002", "100150003"],
        "ano": ["2025", "2026", "2026", "2025"],
        "mes": ["Dezembro", "Janeiro", "Janeiro", "Março"],
    })
    return df, df_custos_raw


def test_sem_selecao_retorna_tudo():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, [], [], [], [])
    assert len(resultado) == 3


def test_filtra_por_projeto():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, ["100150001 Alpha"], [], [], [])
    assert resultado["projeto"].tolist() == ["100150001"]


def test_filtra_por_ano():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, [], ["2026"], [], [])
    assert set(resultado["projeto"]) == {"100150001", "100150002"}


def test_filtra_por_mes():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, [], [], ["Janeiro"], [])
    assert set(resultado["projeto"]) == {"100150001", "100150002"}


def test_filtra_por_status():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, [], [], [], ["Viabilizado", "Cancelado"])
    assert set(resultado["projeto"]) == {"100150001", "100150003"}


def test_combina_multiplos_criterios_com_and():
    df, df_custos_raw = _df_exemplo()
    resultado = aplicar_filtros(df, df_custos_raw, [], ["2026"], [], ["Viabilizado"])
    assert resultado["projeto"].tolist() == ["100150001"]
