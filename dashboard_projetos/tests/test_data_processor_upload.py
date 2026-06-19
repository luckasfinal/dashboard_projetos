from utils.data_processor import processar_arquivo_custos, processar_arquivo_horas
from utils.db import carregar_custos, carregar_horas

MARCADOR = "__teste_pytest__"


class _ArquivoFake:
    def __init__(self, conteudo: bytes, nome: str):
        self._conteudo = conteudo
        self.name = nome

    def read(self):
        return self._conteudo


def _arquivo_custos_valido(nome):
    csv = (
        "Centro de Custo;Ano;Mês;Realizado\n"
        f"100150999;2026;Janeiro;5000,00\n"
    ).encode("utf-8-sig")
    return _ArquivoFake(csv, nome)


def _arquivo_custos_invalido(nome):
    csv = "Coluna Qualquer;Outra Coluna\nx;y\n".encode("utf-8-sig")
    return _ArquivoFake(csv, nome)


def _arquivo_horas_valido(nome):
    csv = (
        "Período;C.Custo;Nome;Hs Nor\n"
        f"01/01/2026;100150999;Colaborador Teste;8\n"
    ).encode("utf-8-sig")
    return _ArquivoFake(csv, nome)


def _arquivo_horas_invalido(nome):
    csv = "Coluna Qualquer;Outra Coluna\nx;y\n".encode("utf-8-sig")
    return _ArquivoFake(csv, nome)


def test_processar_arquivo_custos_sucesso():
    nome = f"custos_a{MARCADOR}.csv"
    resultado = processar_arquivo_custos(_arquivo_custos_valido(nome))

    assert resultado["ok"] is True
    assert "1 linhas" in resultado["mensagem"]
    df = carregar_custos()
    assert (df["arquivo"] == nome).sum() == 1


def test_processar_arquivo_custos_colunas_faltando():
    nome = f"custos_b{MARCADOR}.csv"
    resultado = processar_arquivo_custos(_arquivo_custos_invalido(nome))

    assert resultado["ok"] is False
    assert resultado["colunas"] is not None
    df = carregar_custos()
    assert (df["arquivo"] == nome).sum() == 0


def test_processar_arquivo_custos_duplicado_e_ignorado():
    nome = f"custos_c{MARCADOR}.csv"
    processar_arquivo_custos(_arquivo_custos_valido(nome))
    resultado = processar_arquivo_custos(_arquivo_custos_valido(nome))

    assert resultado["ok"] is False
    assert "já foi importado" in resultado["mensagem"]


def test_processar_arquivo_horas_sucesso():
    nome = f"horas_a{MARCADOR}.csv"
    resultado = processar_arquivo_horas(_arquivo_horas_valido(nome))

    assert resultado["ok"] is True
    assert "1 linhas" in resultado["mensagem"]
    df = carregar_horas()
    assert (df["arquivo"] == nome).sum() == 1


def test_processar_arquivo_horas_colunas_faltando():
    nome = f"horas_b{MARCADOR}.csv"
    resultado = processar_arquivo_horas(_arquivo_horas_invalido(nome))

    assert resultado["ok"] is False
    assert resultado["colunas"] is not None
    df = carregar_horas()
    assert (df["arquivo"] == nome).sum() == 0


def test_processar_arquivo_horas_duplicado_e_ignorado():
    nome = f"horas_c{MARCADOR}.csv"
    processar_arquivo_horas(_arquivo_horas_valido(nome))
    resultado = processar_arquivo_horas(_arquivo_horas_valido(nome))

    assert resultado["ok"] is False
    assert "já foi importado" in resultado["mensagem"]
