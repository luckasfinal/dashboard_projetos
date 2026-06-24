import pytest
import pandas as pd
from utils.dashboard_executivo import (
    categorizar_conta, PALAVRAS_CATEGORIA, CATEGORIAS_CUSTO,
)

def test_categorizar_conta_mao_de_obra():
    assert categorizar_conta("610000 - Mão de Obra Própria") == "Mão de obra"

def test_categorizar_conta_terceiros():
    assert categorizar_conta("720100 - Serviços de Terceiros") == "Terceiros"

def test_categorizar_conta_materiais():
    assert categorizar_conta("510000 - Material de Consumo") == "Materiais"

def test_categorizar_conta_viagens():
    assert categorizar_conta("840000 - Viagem e Hospedagem") == "Viagens"

def test_categorizar_conta_fallback_outras():
    assert categorizar_conta("999999 - Despesas Diversas") == "Outras"

def test_categorizar_conta_vazia():
    assert categorizar_conta("") == "Outras"

def test_categorizar_conta_none():
    assert categorizar_conta(None) == "Outras"

def test_categorizar_conta_case_insensitive():
    assert categorizar_conta("MÃO DE OBRA INDIRETA") == "Mão de obra"

def test_categorias_custo_lista():
    assert set(CATEGORIAS_CUSTO) == {"Mão de obra", "Terceiros", "Materiais", "Viagens"}
