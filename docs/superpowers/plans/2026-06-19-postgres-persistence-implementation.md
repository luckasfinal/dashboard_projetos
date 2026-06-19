# Migração de Persistência (SQLite → Postgres/Supabase) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o SQLite local (`dashboard_projetos/data/dashboard.db`) por um banco Postgres gerenciado no Supabase, eliminando o risco de perda de dados a cada redeploy do Streamlit Community Cloud, sem alterar a interface pública de `utils/db.py`.

**Architecture:** `utils/db.py` é reescrito para usar um `Engine` SQLAlchemy (driver `psycopg2`) cacheado por processo via `st.cache_resource`, mantendo as mesmas funções públicas (mesmos nomes, parâmetros e tipos de retorno) consumidas por `data_processor.py` e pelas páginas. Nenhum outro arquivo de `pages/` precisa mudar.

**Tech Stack:** Python, Streamlit, SQLAlchemy 2.x, psycopg2-binary, pandas, pytest, Supabase (Postgres gerenciado).

## Global Constraints

- Interface pública de `utils/db.py` não muda: mesmos nomes de função, parâmetros e tipos de retorno (`pandas.DataFrame`, `dict`, `tuple[int, bool]`, etc.) — ver spec em `docs/superpowers/specs/2026-06-19-postgres-persistence-design.md`.
- Colunas de data de cronograma (`data_inicio`, `prev_*`, `real_*`) e de timestamp (`importado_em`, `atualizado_em`) permanecem **TEXT**, no formato `YYYY-MM-DD` ou `YYYY-MM-DD HH:MM:SS`, geradas em Python — nunca tipos nativos `DATE`/`TIMESTAMP` do Postgres.
- Toda query SQL usa `sqlalchemy.text(...)` com parâmetros nomeados (`:nome`) e um dict de params — nunca `?` (SQLite) nem `%s` posicional.
- Sem dual-write, sem feature flag, sem fallback SQLite — corte direto (não há dados reais a preservar).
- Sem mudanças em `data_processor.py`, `app.py` ou qualquer arquivo em `pages/`.
- Todos os comandos abaixo assumem o diretório de trabalho `dashboard_projetos/` (onde estão `requirements.txt`, `utils/`, `pages/`).

---

### Task 1: Provisionar Supabase, conexão básica e limpeza do workaround de redeploy

**Files:**
- Create: `dashboard_projetos/utils/db.py` (novo conteúdo — apenas conexão, ainda sem schema/CRUD)
- Create: `dashboard_projetos/tests/conftest.py`
- Create: `dashboard_projetos/tests/test_db_conexao.py`
- Modify: `dashboard_projetos/requirements.txt`
- Create: `dashboard_projetos/requirements-dev.txt`
- Modify: `dashboard_projetos/.env.example`
- Modify: `dashboard_projetos/.streamlit/secrets.toml.example`
- Delete: `.github/workflows/auto-commit.yml`

**Interfaces:**
- Produces: `utils.db._database_url() -> str`, `utils.db._engine() -> sqlalchemy.engine.Engine`, `utils.db._agora() -> str`. Tasks 2–7 importam e usam `_engine()` e `_agora()`.

- [ ] **Step 1: Autenticar no Supabase**

Chame a ferramenta `mcp__plugin_supabase_supabase__authenticate`. Ela devolve uma URL de autorização — peça ao usuário para abrir essa URL no navegador, autorizar, e colar de volta a URL de callback (`http://localhost:<porta>/callback?code=...&state=...`). Em seguida chame `mcp__plugin_supabase_supabase__complete_authentication` com essa `callback_url`.

- [ ] **Step 2: Provisionar um novo projeto Supabase**

Depois da autenticação, novas ferramentas do servidor MCP do Supabase devem aparecer (criação de projeto, leitura de connection string). Use-as para:
1. Criar um novo projeto (nome sugerido: `dashboard-projetos`).
2. Obter a connection string Postgres no formato `postgresql://postgres:<senha>@<host>:5432/postgres` (ou o pooler de conexão recomendado pelo Supabase, se for a opção padrão exibida).

Guarde essa string — ela será usada nos passos seguintes, mas **nunca deve ser commitada**.

- [ ] **Step 3: Adicionar dependências**

Leia o `dashboard_projetos/requirements.txt` atual e adicione as duas linhas abaixo (mantendo as existentes):

```
sqlalchemy
psycopg2-binary
```

Crie `dashboard_projetos/requirements-dev.txt`:

```
-r requirements.txt
pytest
```

Instale localmente:

Run: `pip install -r dashboard_projetos/requirements-dev.txt`
Expected: instalação concluída sem erros, incluindo `sqlalchemy`, `psycopg2-binary` e `pytest`.

- [ ] **Step 4: Configurar a connection string localmente**

Crie (ou edite) `dashboard_projetos/.streamlit/secrets.toml` (este arquivo é local, **não é commitado** — já está no `.gitignore`) com o conteúdo:

```toml
DATABASE_URL = "postgresql://postgres:SENHA_REAL@HOST_REAL:5432/postgres"
```

(Substitua pela connection string real obtida no Step 2. Se o arquivo já existir com `AUTH_USERS`, apenas adicione a linha `DATABASE_URL` a ele.)

- [ ] **Step 5: Escrever o teste de conectividade (vai falhar)**

Crie `dashboard_projetos/tests/conftest.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in [str(ROOT), str(ROOT / "utils")]:
    if p not in sys.path:
        sys.path.insert(0, p)
```

Crie `dashboard_projetos/tests/test_db_conexao.py`:

```python
from sqlalchemy import text
from utils.db import _engine


def test_consegue_conectar_no_postgres():
    with _engine().connect() as con:
        resultado = con.execute(text("SELECT 1")).scalar()
    assert resultado == 1
```

- [ ] **Step 6: Rodar o teste e confirmar que falha**

Run: `cd dashboard_projetos && pytest tests/test_db_conexao.py -v`
Expected: FAIL — `ModuleNotFoundError` ou `ImportError` (`utils.db` ainda não define `_engine`, pois o arquivo antigo baseado em SQLite ainda está no lugar).

- [ ] **Step 7: Criar o novo `utils/db.py` (apenas conexão)**

Substitua **todo** o conteúdo de `dashboard_projetos/utils/db.py` por:

```python
"""
db.py — camada de persistência Postgres (Supabase)
- Schema idempotente (CREATE TABLE IF NOT EXISTS + migração de colunas)
- Conexão via SQLAlchemy Engine, cacheada por processo (st.cache_resource)
- Suporte a nomes de projeto editáveis e previsões por período
"""
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _database_url() -> str:
    """
    Retorna a connection string Postgres a partir de st.secrets (produção)
    ou variável de ambiente DATABASE_URL (uso local).
    """
    try:
        if "DATABASE_URL" in st.secrets:
            return str(st.secrets["DATABASE_URL"])
    except Exception:
        pass
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL não configurado. Defina nos Secrets do Streamlit "
            "Cloud (produção) ou em .streamlit/secrets.toml / variável de "
            "ambiente (uso local)."
        )
    return url


@st.cache_resource(show_spinner=False)
def _engine() -> Engine:
    return create_engine(_database_url(), pool_pre_ping=True)


def _agora() -> str:
    """Timestamp atual no formato usado pelas colunas TEXT de data/hora."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```

- [ ] **Step 8: Rodar o teste de conectividade e confirmar que passa**

Run: `cd dashboard_projetos && pytest tests/test_db_conexao.py -v`
Expected: PASS — `test_consegue_conectar_no_postgres`.

Se falhar com erro de conexão (timeout, autenticação), revise a connection string no `secrets.toml` antes de seguir.

- [ ] **Step 9: Atualizar exemplos de configuração**

No `dashboard_projetos/.env.example`, adicione ao final do arquivo:

```
# ----------------------------------------------------------------------------
# DATABASE_URL — connection string do Postgres (Supabase).
#
# Formato: postgresql://usuario:senha@host:porta/banco
# Obtenha em: Supabase -> Project Settings -> Database -> Connection string.
#
# Em PRODUÇÃO (Streamlit Community Cloud) NÃO se usa .env: a connection
# string vai no painel "Secrets" do app, igual ao AUTH_USERS.
# ----------------------------------------------------------------------------
DATABASE_URL="postgresql://postgres:COLE_A_SENHA_REAL@COLE_O_HOST_REAL:5432/postgres"
```

No `dashboard_projetos/.streamlit/secrets.toml.example`, adicione ao final do arquivo:

```toml

# Connection string Postgres (Supabase) — ver .env.example para detalhes.
DATABASE_URL = "postgresql://postgres:COLE_A_SENHA_REAL@COLE_O_HOST_REAL:5432/postgres"
```

- [ ] **Step 10: Remover o workflow de commit automático**

Delete o arquivo `.github/workflows/auto-commit.yml` (caminho na raiz do repositório, fora de `dashboard_projetos/`). Esse workflow criava um commit vazio a cada 4 horas, o que dispara redeploy no Streamlit Cloud e, com armazenamento efêmero, podia apagar dados — sem mais utilidade após esta migração.

- [ ] **Step 11: Commit**

```bash
git add dashboard_projetos/utils/db.py dashboard_projetos/tests/conftest.py dashboard_projetos/tests/test_db_conexao.py dashboard_projetos/requirements.txt dashboard_projetos/requirements-dev.txt dashboard_projetos/.env.example "dashboard_projetos/.streamlit/secrets.toml.example"
git rm .github/workflows/auto-commit.yml
git commit -m "feat: inicia migracao de persistencia para Postgres (Supabase)

Adiciona conexao SQLAlchemy/psycopg2 cacheada, remove workflow de
commit automatico que forcava redeploys desnecessarios."
```

(Não commite `dashboard_projetos/.streamlit/secrets.toml` nem qualquer arquivo com a connection string real — confirme que `git status` não o lista como staged.)

---

### Task 2: Schema (`init_db`/`migrar_db`) e scaffolding de testes

**Files:**
- Modify: `dashboard_projetos/utils/db.py` (adicionar ao final)
- Modify: `dashboard_projetos/tests/conftest.py` (expandir)
- Create: `dashboard_projetos/tests/test_db_schema.py`

**Interfaces:**
- Consumes: `utils.db._engine()`, `utils.db._agora()` (Task 1).
- Produces: `utils.db.init_db()`, `utils.db.migrar_db()`, `utils.db.COLUNAS_DB_CUSTOS`, `utils.db.COLUNAS_DB_HORAS`, `utils.db.COLUNAS_DB_ORCAMENTOS`, `utils.db.STATUS_OPCOES`, `utils.db.STATUS_DEFAULT`. Tasks 3–7 usam essas constantes e chamam `init_db()`/`migrar_db()` via fixture de sessão.

- [ ] **Step 1: Escrever o teste de schema (vai falhar)**

Crie `dashboard_projetos/tests/test_db_schema.py`:

```python
from sqlalchemy import text
from utils.db import _engine, init_db, migrar_db


def test_tabelas_sao_criadas():
    init_db()
    with _engine().connect() as con:
        tabelas = {
            row[0] for row in con.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            ).fetchall()
        }
    esperadas = {
        "custos", "horas", "importacoes",
        "orcamentos_cronograma", "previsoes_periodo",
    }
    assert esperadas.issubset(tabelas)


def test_migrar_db_e_idempotente():
    init_db()
    migrar_db()
    migrar_db()  # rodar duas vezes não deve lançar erro
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd dashboard_projetos && pytest tests/test_db_schema.py -v`
Expected: FAIL — `ImportError: cannot import name 'init_db'`.

- [ ] **Step 3: Adicionar schema a `utils/db.py`**

Acrescente ao final de `dashboard_projetos/utils/db.py`:

```python

# ─────────────────────────────────────────────────────
# Colunas esperadas por tabela
# ─────────────────────────────────────────────────────

COLUNAS_DB_CUSTOS = [
    "data", "ano", "mes", "filial", "area",
    "centro_de_custo", "conta", "cod_parceiro_negocio",
    "parceiro_negocio", "historico", "realizado",
]

COLUNAS_DB_HORAS = [
    "periodo", "c_custo", "ordem_interna", "descricao_ordem_interna",
    "centro_de_lucro", "descricao_c_lucro", "matricula", "nome",
    "cc_origem", "descricao_cc_origem", "hs_nor", "tipo_de_projeto",
    "cod_produto", "descricao_produto", "categoria", "atividade",
    "detalhes", "c_custo_descricao_ordem_interna", "matricula_nome", "segmento",
]

COLUNAS_DB_ORCAMENTOS = [
    "projeto", "nome_projeto_editado", "orcamento_previsto",
    "status_projeto",
    "data_inicio",
    "prev_viabilidade", "prev_qualidade", "prev_aprov_lancamento", "prev_lancamento",
    "real_viabilidade", "real_qualidade", "real_aprov_lancamento", "real_lancamento",
]

# ── Status do Projeto — opções fixas do dropdown ──────────────────────────────
STATUS_OPCOES = [
    "CC criado",
    "Viabilizado",
    "Aprovado em Critérios de Qualidade",
    "Aprovado para Lançamento",
    "Lançado",
    "Stand by",
    "Cancelado",
]
STATUS_DEFAULT = STATUS_OPCOES[0]

TIPOS_CUSTOS = {
    "data": "TEXT", "ano": "TEXT", "mes": "TEXT", "filial": "TEXT",
    "area": "TEXT", "centro_de_custo": "TEXT", "conta": "TEXT",
    "cod_parceiro_negocio": "TEXT", "parceiro_negocio": "TEXT",
    "historico": "TEXT", "realizado": "DOUBLE PRECISION",
}

TIPOS_HORAS = {
    "periodo": "TEXT", "c_custo": "TEXT", "ordem_interna": "TEXT",
    "descricao_ordem_interna": "TEXT", "centro_de_lucro": "TEXT",
    "descricao_c_lucro": "TEXT", "matricula": "TEXT", "nome": "TEXT",
    "cc_origem": "TEXT", "descricao_cc_origem": "TEXT", "hs_nor": "DOUBLE PRECISION",
    "tipo_de_projeto": "TEXT", "cod_produto": "TEXT", "descricao_produto": "TEXT",
    "categoria": "TEXT", "atividade": "TEXT", "detalhes": "TEXT",
    "c_custo_descricao_ordem_interna": "TEXT", "matricula_nome": "TEXT",
    "segmento": "TEXT",
}

TIPOS_ORCAMENTOS = {
    "projeto": "TEXT", "nome_projeto_editado": "TEXT",
    "orcamento_previsto": "DOUBLE PRECISION", "status_projeto": "TEXT",
    "data_inicio": "TEXT",
    "prev_viabilidade": "TEXT", "prev_qualidade": "TEXT",
    "prev_aprov_lancamento": "TEXT", "prev_lancamento": "TEXT",
    "real_viabilidade": "TEXT", "real_qualidade": "TEXT",
    "real_aprov_lancamento": "TEXT", "real_lancamento": "TEXT",
}


def init_db() -> None:
    """Cria tabelas se não existirem."""
    with _engine().begin() as con:
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS custos (
                id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                arquivo      TEXT NOT NULL,
                importado_em TEXT NOT NULL,
                data TEXT, ano TEXT, mes TEXT, filial TEXT, area TEXT,
                centro_de_custo TEXT, conta TEXT, cod_parceiro_negocio TEXT,
                parceiro_negocio TEXT, historico TEXT, realizado DOUBLE PRECISION
            )
        """))
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS horas (
                id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                arquivo      TEXT NOT NULL,
                importado_em TEXT NOT NULL,
                periodo TEXT, c_custo TEXT, ordem_interna TEXT,
                descricao_ordem_interna TEXT, centro_de_lucro TEXT,
                descricao_c_lucro TEXT, matricula TEXT, nome TEXT,
                cc_origem TEXT, descricao_cc_origem TEXT, hs_nor DOUBLE PRECISION,
                tipo_de_projeto TEXT, cod_produto TEXT, descricao_produto TEXT,
                categoria TEXT, atividade TEXT, detalhes TEXT,
                c_custo_descricao_ordem_interna TEXT, matricula_nome TEXT,
                segmento TEXT
            )
        """))
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS importacoes (
                id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                arquivo      TEXT NOT NULL,
                tipo         TEXT NOT NULL,
                importado_em TEXT NOT NULL,
                linhas       INTEGER
            )
        """))
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS orcamentos_cronograma (
                projeto                 TEXT PRIMARY KEY,
                nome_projeto_editado    TEXT,
                orcamento_previsto      DOUBLE PRECISION DEFAULT 0,
                status_projeto          TEXT DEFAULT 'CC criado',
                data_inicio             TEXT,
                prev_viabilidade        TEXT,
                prev_qualidade          TEXT,
                prev_aprov_lancamento   TEXT,
                prev_lancamento         TEXT,
                real_viabilidade        TEXT,
                real_qualidade          TEXT,
                real_aprov_lancamento   TEXT,
                real_lancamento         TEXT,
                atualizado_em           TEXT
            )
        """))
        con.execute(text("""
            CREATE TABLE IF NOT EXISTS previsoes_periodo (
                id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                projeto       TEXT NOT NULL,
                periodo       TEXT NOT NULL,
                tipo_periodo  TEXT NOT NULL DEFAULT 'anual',
                descricao     TEXT,
                valor         DOUBLE PRECISION NOT NULL DEFAULT 0,
                atualizado_em TEXT,
                UNIQUE(projeto, periodo, tipo_periodo)
            )
        """))


def migrar_db() -> None:
    """Migração não-destrutiva: adiciona colunas novas sem apagar dados."""
    with _engine().begin() as con:
        for tabela, colunas, tipos in [
            ("custos",                COLUNAS_DB_CUSTOS,     TIPOS_CUSTOS),
            ("horas",                 COLUNAS_DB_HORAS,      TIPOS_HORAS),
            ("orcamentos_cronograma", COLUNAS_DB_ORCAMENTOS, TIPOS_ORCAMENTOS),
        ]:
            existentes = {
                row[0] for row in con.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = :tabela"
                    ),
                    {"tabela": tabela},
                ).fetchall()
            }
            for col in colunas:
                if col not in existentes:
                    tipo = tipos.get(col, "TEXT")
                    con.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {col} {tipo}"))
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd dashboard_projetos && pytest tests/test_db_schema.py -v`
Expected: PASS — `test_tabelas_sao_criadas`, `test_migrar_db_e_idempotente`.

- [ ] **Step 5: Expandir `conftest.py` para inicializar o schema uma vez por sessão**

Substitua o conteúdo de `dashboard_projetos/tests/conftest.py` por:

```python
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in [str(ROOT), str(ROOT / "utils")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import text  # noqa: E402
from utils.db import init_db, migrar_db, _engine  # noqa: E402

MARCADOR_TESTE = "__teste_pytest__"


@pytest.fixture(scope="session", autouse=True)
def _preparar_schema():
    init_db()
    migrar_db()


@pytest.fixture(autouse=True)
def _limpar_dados_de_teste():
    yield
    with _engine().begin() as con:
        con.execute(text("DELETE FROM custos WHERE arquivo LIKE :m"), {"m": f"%{MARCADOR_TESTE}%"})
        con.execute(text("DELETE FROM horas WHERE arquivo LIKE :m"), {"m": f"%{MARCADOR_TESTE}%"})
        con.execute(text("DELETE FROM importacoes WHERE arquivo LIKE :m"), {"m": f"%{MARCADOR_TESTE}%"})
        con.execute(text("DELETE FROM orcamentos_cronograma WHERE projeto LIKE :m"), {"m": f"%{MARCADOR_TESTE}%"})
        con.execute(text("DELETE FROM previsoes_periodo WHERE projeto LIKE :m"), {"m": f"%{MARCADOR_TESTE}%"})
```

- [ ] **Step 6: Rodar toda a suíte e confirmar que nada quebrou**

Run: `cd dashboard_projetos && pytest tests/ -v`
Expected: PASS em todos os testes existentes (`test_db_conexao.py`, `test_db_schema.py`).

- [ ] **Step 7: Commit**

```bash
git add dashboard_projetos/utils/db.py dashboard_projetos/tests/conftest.py dashboard_projetos/tests/test_db_schema.py
git commit -m "feat: adiciona schema Postgres (init_db/migrar_db) e fixtures de teste"
```

---

### Task 3: Custos & importações

**Files:**
- Modify: `dashboard_projetos/utils/db.py` (adicionar ao final)
- Create: `dashboard_projetos/tests/test_db_custos.py`

**Interfaces:**
- Consumes: `utils.db._engine()`, `utils.db._agora()`, `utils.db.COLUNAS_DB_CUSTOS` (Tasks 1–2).
- Produces: `utils.db._ja_importado(arquivo: str, tipo: str) -> bool`, `utils.db.salvar_custos(df, nome_arquivo) -> tuple[int, bool]`, `utils.db.carregar_custos() -> pd.DataFrame`, `utils.db.listar_importacoes() -> pd.DataFrame`, `utils.db.deletar_importacao(nome_arquivo, tipo) -> int`. Task 4 reutiliza `_ja_importado`; Task 7 usa `carregar_custos`.

- [ ] **Step 1: Escrever os testes (vão falhar)**

Crie `dashboard_projetos/tests/test_db_custos.py`:

```python
import pandas as pd
from utils.db import salvar_custos, carregar_custos, listar_importacoes, deletar_importacao

ARQUIVO_TESTE = "custos__teste_pytest__.csv"


def _df_custos_exemplo():
    return pd.DataFrame({
        "centro_de_custo": ["100150268"],
        "ano": ["2026"],
        "mes": ["Janeiro"],
        "realizado": [1000.50],
    })


def test_salvar_e_carregar_custos():
    linhas, duplicado = salvar_custos(_df_custos_exemplo(), ARQUIVO_TESTE)
    assert linhas == 1
    assert duplicado is False

    df = carregar_custos()
    assert (df["arquivo"] == ARQUIVO_TESTE).sum() == 1
    linha = df[df["arquivo"] == ARQUIVO_TESTE].iloc[0]
    assert linha["centro_de_custo"] == "100150268"
    assert float(linha["realizado"]) == 1000.50


def test_salvar_custos_duplicado_e_ignorado():
    salvar_custos(_df_custos_exemplo(), ARQUIVO_TESTE)
    linhas, duplicado = salvar_custos(_df_custos_exemplo(), ARQUIVO_TESTE)
    assert linhas == 0
    assert duplicado is True


def test_listar_importacoes_inclui_arquivo_salvo():
    salvar_custos(_df_custos_exemplo(), ARQUIVO_TESTE)
    df_imp = listar_importacoes()
    assert (df_imp["arquivo"] == ARQUIVO_TESTE).any()


def test_deletar_importacao_remove_linhas():
    salvar_custos(_df_custos_exemplo(), ARQUIVO_TESTE)
    removidas = deletar_importacao(ARQUIVO_TESTE, "custos")
    assert removidas == 1
    df = carregar_custos()
    assert (df["arquivo"] == ARQUIVO_TESTE).sum() == 0
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd dashboard_projetos && pytest tests/test_db_custos.py -v`
Expected: FAIL — `ImportError: cannot import name 'salvar_custos'`.

- [ ] **Step 3: Implementar em `utils/db.py`**

Acrescente ao final de `dashboard_projetos/utils/db.py`:

```python

# ─────────────────────────────────────────────────────
# Gravação e leitura — custos
# ─────────────────────────────────────────────────────

def _ja_importado(arquivo: str, tipo: str) -> bool:
    with _engine().connect() as con:
        row = con.execute(
            text("SELECT 1 FROM importacoes WHERE arquivo = :arquivo AND tipo = :tipo LIMIT 1"),
            {"arquivo": arquivo, "tipo": tipo},
        ).fetchone()
        return row is not None


def salvar_custos(df: pd.DataFrame, nome_arquivo: str) -> tuple[int, bool]:
    if _ja_importado(nome_arquivo, "custos"):
        return 0, True
    df_ins = df.reindex(columns=COLUNAS_DB_CUSTOS)
    df_ins["arquivo"] = nome_arquivo
    df_ins["importado_em"] = _agora()
    with _engine().begin() as con:
        df_ins.to_sql("custos", con, if_exists="append", index=False)
        con.execute(
            text(
                "INSERT INTO importacoes (arquivo, tipo, linhas, importado_em) "
                "VALUES (:arquivo, 'custos', :linhas, :agora)"
            ),
            {"arquivo": nome_arquivo, "linhas": len(df_ins), "agora": _agora()},
        )
    return len(df_ins), False


def carregar_custos() -> pd.DataFrame:
    with _engine().connect() as con:
        return pd.read_sql(text("SELECT * FROM custos"), con)


def listar_importacoes() -> pd.DataFrame:
    with _engine().connect() as con:
        return pd.read_sql(
            text(
                "SELECT tipo, arquivo, importado_em, linhas FROM importacoes "
                "ORDER BY importado_em DESC"
            ),
            con,
        )


def deletar_importacao(nome_arquivo: str, tipo: str) -> int:
    tabela = "custos" if tipo == "custos" else "horas"
    with _engine().begin() as con:
        resultado = con.execute(
            text(f"DELETE FROM {tabela} WHERE arquivo = :arquivo"),
            {"arquivo": nome_arquivo},
        )
        con.execute(
            text("DELETE FROM importacoes WHERE arquivo = :arquivo AND tipo = :tipo"),
            {"arquivo": nome_arquivo, "tipo": tipo},
        )
        return resultado.rowcount
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd dashboard_projetos && pytest tests/test_db_custos.py -v`
Expected: PASS em todos os 4 testes.

- [ ] **Step 5: Commit**

```bash
git add dashboard_projetos/utils/db.py dashboard_projetos/tests/test_db_custos.py
git commit -m "feat: implementa custos e importacoes na camada Postgres"
```

---

### Task 4: Horas

**Files:**
- Modify: `dashboard_projetos/utils/db.py` (adicionar ao final)
- Create: `dashboard_projetos/tests/test_db_horas.py`

**Interfaces:**
- Consumes: `utils.db._engine()`, `utils.db._agora()`, `utils.db._ja_importado()`, `utils.db.COLUNAS_DB_HORAS` (Tasks 1–3).
- Produces: `utils.db.salvar_horas(df, nome_arquivo) -> tuple[int, bool]`, `utils.db.carregar_horas() -> pd.DataFrame`. Task 7 usa `carregar_horas`.

- [ ] **Step 1: Escrever os testes (vão falhar)**

Crie `dashboard_projetos/tests/test_db_horas.py`:

```python
import pandas as pd
from utils.db import salvar_horas, carregar_horas

ARQUIVO_TESTE = "horas__teste_pytest__.csv"


def _df_horas_exemplo():
    return pd.DataFrame({
        "c_custo": ["100150268"],
        "nome": ["Colaborador Teste"],
        "periodo": ["01/01/2026"],
        "hs_nor": [8.0],
    })


def test_salvar_e_carregar_horas():
    linhas, duplicado = salvar_horas(_df_horas_exemplo(), ARQUIVO_TESTE)
    assert linhas == 1
    assert duplicado is False

    df = carregar_horas()
    linha = df[df["arquivo"] == ARQUIVO_TESTE].iloc[0]
    assert linha["c_custo"] == "100150268"
    assert float(linha["hs_nor"]) == 8.0


def test_salvar_horas_duplicado_e_ignorado():
    salvar_horas(_df_horas_exemplo(), ARQUIVO_TESTE)
    linhas, duplicado = salvar_horas(_df_horas_exemplo(), ARQUIVO_TESTE)
    assert linhas == 0
    assert duplicado is True
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd dashboard_projetos && pytest tests/test_db_horas.py -v`
Expected: FAIL — `ImportError: cannot import name 'salvar_horas'`.

- [ ] **Step 3: Implementar em `utils/db.py`**

Acrescente ao final de `dashboard_projetos/utils/db.py`:

```python

# ─────────────────────────────────────────────────────
# Gravação e leitura — horas
# ─────────────────────────────────────────────────────

def salvar_horas(df: pd.DataFrame, nome_arquivo: str) -> tuple[int, bool]:
    if _ja_importado(nome_arquivo, "horas"):
        return 0, True
    df_ins = df.reindex(columns=COLUNAS_DB_HORAS)
    df_ins["arquivo"] = nome_arquivo
    df_ins["importado_em"] = _agora()
    with _engine().begin() as con:
        df_ins.to_sql("horas", con, if_exists="append", index=False)
        con.execute(
            text(
                "INSERT INTO importacoes (arquivo, tipo, linhas, importado_em) "
                "VALUES (:arquivo, 'horas', :linhas, :agora)"
            ),
            {"arquivo": nome_arquivo, "linhas": len(df_ins), "agora": _agora()},
        )
    return len(df_ins), False


def carregar_horas() -> pd.DataFrame:
    with _engine().connect() as con:
        return pd.read_sql(text("SELECT * FROM horas"), con)
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd dashboard_projetos && pytest tests/test_db_horas.py -v`
Expected: PASS nos 2 testes.

- [ ] **Step 5: Commit**

```bash
git add dashboard_projetos/utils/db.py dashboard_projetos/tests/test_db_horas.py
git commit -m "feat: implementa horas na camada Postgres"
```

---

### Task 5: Orçamentos e cronograma

**Files:**
- Modify: `dashboard_projetos/utils/db.py` (adicionar ao final)
- Create: `dashboard_projetos/tests/test_db_orcamentos.py`

**Interfaces:**
- Consumes: `utils.db._engine()`, `utils.db._agora()` (Task 1).
- Produces: `utils.db.salvar_orcamento(...) -> None`, `utils.db.carregar_orcamentos() -> pd.DataFrame`, `utils.db.carregar_orcamento_projeto(projeto: str) -> dict | None`, `utils.db.deletar_orcamento_projeto(projeto: str) -> bool`. Task 7 usa `carregar_orcamento_projeto` e a tabela `orcamentos_cronograma`.

- [ ] **Step 1: Escrever os testes (vão falhar)**

Crie `dashboard_projetos/tests/test_db_orcamentos.py`:

```python
from utils.db import (
    salvar_orcamento, carregar_orcamento_projeto, carregar_orcamentos,
    deletar_orcamento_projeto,
)

PROJETO_TESTE = "PROJ__teste_pytest__"


def _salvar_orcamento_exemplo(orcamento=5000.0, status="Viabilizado"):
    salvar_orcamento(
        projeto=PROJETO_TESTE,
        orcamento_previsto=orcamento,
        status_projeto=status,
        data_inicio="2026-01-01",
        prev_viabilidade="2026-02-01",
        prev_qualidade=None,
        prev_aprov_lancamento=None,
        prev_lancamento="2026-06-01",
        real_viabilidade=None,
        real_qualidade=None,
        real_aprov_lancamento=None,
        real_lancamento=None,
        nome_projeto_editado="Projeto de Teste",
    )


def test_salvar_e_carregar_orcamento():
    _salvar_orcamento_exemplo()
    dados = carregar_orcamento_projeto(PROJETO_TESTE)
    assert dados is not None
    assert dados["projeto"] == PROJETO_TESTE
    assert float(dados["orcamento_previsto"]) == 5000.0
    assert dados["status_projeto"] == "Viabilizado"
    assert dados["nome_projeto_editado"] == "Projeto de Teste"
    assert dados["data_inicio"] == "2026-01-01"


def test_salvar_orcamento_e_upsert():
    _salvar_orcamento_exemplo(orcamento=5000.0, status="Viabilizado")
    _salvar_orcamento_exemplo(orcamento=7500.0, status="Lançado")

    dados = carregar_orcamento_projeto(PROJETO_TESTE)
    assert float(dados["orcamento_previsto"]) == 7500.0
    assert dados["status_projeto"] == "Lançado"

    todos = carregar_orcamentos()
    assert (todos["projeto"] == PROJETO_TESTE).sum() == 1  # upsert, não duplica


def test_deletar_orcamento_projeto():
    _salvar_orcamento_exemplo()
    removido = deletar_orcamento_projeto(PROJETO_TESTE)
    assert removido is True
    assert carregar_orcamento_projeto(PROJETO_TESTE) is None
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd dashboard_projetos && pytest tests/test_db_orcamentos.py -v`
Expected: FAIL — `ImportError: cannot import name 'salvar_orcamento'`.

- [ ] **Step 3: Implementar em `utils/db.py`**

Acrescente ao final de `dashboard_projetos/utils/db.py`:

```python

# ─────────────────────────────────────────────────────
# Gravação e leitura — orçamentos / cronograma
# ─────────────────────────────────────────────────────

def salvar_orcamento(
    projeto: str,
    orcamento_previsto: float,
    data_inicio: str | None,
    prev_viabilidade: str | None,
    prev_qualidade: str | None,
    prev_aprov_lancamento: str | None,
    prev_lancamento: str | None,
    real_viabilidade: str | None,
    real_qualidade: str | None,
    real_aprov_lancamento: str | None,
    real_lancamento: str | None,
    nome_projeto_editado: str | None = None,
    status_projeto: str | None = None,
) -> None:
    with _engine().begin() as con:
        con.execute(text("""
            INSERT INTO orcamentos_cronograma (
                projeto, nome_projeto_editado, orcamento_previsto, status_projeto, data_inicio,
                prev_viabilidade, prev_qualidade, prev_aprov_lancamento, prev_lancamento,
                real_viabilidade, real_qualidade, real_aprov_lancamento, real_lancamento,
                atualizado_em
            ) VALUES (
                :projeto, :nome_projeto_editado, :orcamento_previsto, :status_projeto, :data_inicio,
                :prev_viabilidade, :prev_qualidade, :prev_aprov_lancamento, :prev_lancamento,
                :real_viabilidade, :real_qualidade, :real_aprov_lancamento, :real_lancamento,
                :atualizado_em
            )
            ON CONFLICT (projeto) DO UPDATE SET
                nome_projeto_editado    = excluded.nome_projeto_editado,
                orcamento_previsto      = excluded.orcamento_previsto,
                status_projeto          = excluded.status_projeto,
                data_inicio             = excluded.data_inicio,
                prev_viabilidade        = excluded.prev_viabilidade,
                prev_qualidade          = excluded.prev_qualidade,
                prev_aprov_lancamento   = excluded.prev_aprov_lancamento,
                prev_lancamento         = excluded.prev_lancamento,
                real_viabilidade        = excluded.real_viabilidade,
                real_qualidade          = excluded.real_qualidade,
                real_aprov_lancamento   = excluded.real_aprov_lancamento,
                real_lancamento         = excluded.real_lancamento,
                atualizado_em           = excluded.atualizado_em
        """), {
            "projeto": projeto,
            "nome_projeto_editado": nome_projeto_editado,
            "orcamento_previsto": orcamento_previsto,
            "status_projeto": status_projeto,
            "data_inicio": data_inicio,
            "prev_viabilidade": prev_viabilidade,
            "prev_qualidade": prev_qualidade,
            "prev_aprov_lancamento": prev_aprov_lancamento,
            "prev_lancamento": prev_lancamento,
            "real_viabilidade": real_viabilidade,
            "real_qualidade": real_qualidade,
            "real_aprov_lancamento": real_aprov_lancamento,
            "real_lancamento": real_lancamento,
            "atualizado_em": _agora(),
        })


def carregar_orcamentos() -> pd.DataFrame:
    with _engine().connect() as con:
        return pd.read_sql(text("SELECT * FROM orcamentos_cronograma"), con)


def carregar_orcamento_projeto(projeto: str) -> dict | None:
    with _engine().connect() as con:
        resultado = con.execute(
            text("SELECT * FROM orcamentos_cronograma WHERE projeto = :projeto"),
            {"projeto": projeto},
        )
        linha = resultado.fetchone()
        if linha is None:
            return None
        return dict(linha._mapping)


def deletar_orcamento_projeto(projeto: str) -> bool:
    with _engine().begin() as con:
        resultado = con.execute(
            text("DELETE FROM orcamentos_cronograma WHERE projeto = :projeto"),
            {"projeto": projeto},
        )
        return resultado.rowcount > 0
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd dashboard_projetos && pytest tests/test_db_orcamentos.py -v`
Expected: PASS nos 3 testes.

- [ ] **Step 5: Commit**

```bash
git add dashboard_projetos/utils/db.py dashboard_projetos/tests/test_db_orcamentos.py
git commit -m "feat: implementa orcamentos e cronograma na camada Postgres"
```

---

### Task 6: Previsões por período

**Files:**
- Modify: `dashboard_projetos/utils/db.py` (adicionar ao final)
- Create: `dashboard_projetos/tests/test_db_previsoes.py`

**Interfaces:**
- Consumes: `utils.db._engine()`, `utils.db._agora()` (Task 1).
- Produces: `utils.db.salvar_previsao_periodo(...) -> None`, `utils.db.deletar_previsao_periodo(id_previsao: int) -> None`, `utils.db.carregar_previsoes_projeto(projeto: str) -> pd.DataFrame`, `utils.db.carregar_todas_previsoes() -> pd.DataFrame`. Task 7 usa `carregar_previsoes_projeto` e a tabela `previsoes_periodo`.

- [ ] **Step 1: Escrever os testes (vão falhar)**

Crie `dashboard_projetos/tests/test_db_previsoes.py`:

```python
from utils.db import (
    salvar_previsao_periodo, carregar_previsoes_projeto,
    carregar_todas_previsoes, deletar_previsao_periodo,
)

PROJETO_TESTE = "PROJ__teste_pytest__"


def test_salvar_e_carregar_previsao():
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 10000.0, "anual", "Previsão inicial")
    df = carregar_previsoes_projeto(PROJETO_TESTE)
    assert len(df) == 1
    assert df.iloc[0]["periodo"] == "2026"
    assert float(df.iloc[0]["valor"]) == 10000.0


def test_salvar_previsao_e_upsert_por_periodo_e_tipo():
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 10000.0, "anual")
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 12000.0, "anual")
    df = carregar_previsoes_projeto(PROJETO_TESTE)
    assert len(df) == 1
    assert float(df.iloc[0]["valor"]) == 12000.0


def test_carregar_todas_previsoes_inclui_projeto_teste():
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 10000.0, "anual")
    df = carregar_todas_previsoes()
    assert (df["projeto"] == PROJETO_TESTE).any()


def test_deletar_previsao_periodo():
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 10000.0, "anual")
    df = carregar_previsoes_projeto(PROJETO_TESTE)
    id_prev = int(df.iloc[0]["id"])
    deletar_previsao_periodo(id_prev)
    df_depois = carregar_previsoes_projeto(PROJETO_TESTE)
    assert df_depois.empty
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd dashboard_projetos && pytest tests/test_db_previsoes.py -v`
Expected: FAIL — `ImportError: cannot import name 'salvar_previsao_periodo'`.

- [ ] **Step 3: Implementar em `utils/db.py`**

Acrescente ao final de `dashboard_projetos/utils/db.py`:

```python

# ─────────────────────────────────────────────────────
# Previsões por período
# ─────────────────────────────────────────────────────

def salvar_previsao_periodo(
    projeto: str,
    periodo: str,
    valor: float,
    tipo_periodo: str = "anual",
    descricao: str | None = None,
) -> None:
    """Insere ou atualiza previsão orçamentária de um período."""
    with _engine().begin() as con:
        con.execute(text("""
            INSERT INTO previsoes_periodo (projeto, periodo, tipo_periodo, descricao, valor, atualizado_em)
            VALUES (:projeto, :periodo, :tipo_periodo, :descricao, :valor, :atualizado_em)
            ON CONFLICT (projeto, periodo, tipo_periodo) DO UPDATE SET
                descricao     = excluded.descricao,
                valor         = excluded.valor,
                atualizado_em = excluded.atualizado_em
        """), {
            "projeto": projeto,
            "periodo": periodo,
            "tipo_periodo": tipo_periodo,
            "descricao": descricao,
            "valor": valor,
            "atualizado_em": _agora(),
        })


def deletar_previsao_periodo(id_previsao: int) -> None:
    with _engine().begin() as con:
        con.execute(text("DELETE FROM previsoes_periodo WHERE id = :id"), {"id": id_previsao})


def carregar_previsoes_projeto(projeto: str) -> pd.DataFrame:
    with _engine().connect() as con:
        return pd.read_sql(
            text(
                "SELECT * FROM previsoes_periodo WHERE projeto = :projeto "
                "ORDER BY periodo, tipo_periodo"
            ),
            con, params={"projeto": projeto},
        )


def carregar_todas_previsoes() -> pd.DataFrame:
    with _engine().connect() as con:
        return pd.read_sql(
            text("SELECT * FROM previsoes_periodo ORDER BY projeto, periodo"), con,
        )
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd dashboard_projetos && pytest tests/test_db_previsoes.py -v`
Expected: PASS nos 4 testes.

- [ ] **Step 5: Commit**

```bash
git add dashboard_projetos/utils/db.py dashboard_projetos/tests/test_db_previsoes.py
git commit -m "feat: implementa previsoes por periodo na camada Postgres"
```

---

### Task 7: Deleção em massa

**Files:**
- Modify: `dashboard_projetos/utils/db.py` (adicionar ao final)
- Create: `dashboard_projetos/tests/test_db_delecao.py`

**Interfaces:**
- Consumes: `utils.db._engine()`, `utils.db.salvar_custos`, `utils.db.salvar_horas`, `utils.db.salvar_orcamento`, `utils.db.salvar_previsao_periodo`, `utils.db.carregar_custos`, `utils.db.carregar_horas`, `utils.db.carregar_orcamento_projeto`, `utils.db.carregar_previsoes_projeto` (Tasks 1–6).
- Produces: `utils.db.deletar_projeto_completo(projeto: str) -> dict`, `utils.db.limpar_tudo() -> None`. Nenhuma task posterior depende destas — são as últimas funções públicas de `db.py`.

- [ ] **Step 1: Escrever os testes (vão falhar)**

Crie `dashboard_projetos/tests/test_db_delecao.py`:

```python
import pandas as pd
from utils.db import (
    salvar_custos, salvar_horas, salvar_orcamento, salvar_previsao_periodo,
    deletar_projeto_completo, limpar_tudo, carregar_custos, carregar_horas,
    carregar_orcamento_projeto, carregar_previsoes_projeto,
)

PROJETO_TESTE = "100199__teste_pytest__"
ARQUIVO_CUSTOS = "custos_delecao__teste_pytest__.csv"
ARQUIVO_HORAS = "horas_delecao__teste_pytest__.csv"


def _popular_projeto_teste():
    salvar_custos(pd.DataFrame({
        "centro_de_custo": [PROJETO_TESTE], "ano": ["2026"], "mes": ["Janeiro"], "realizado": [100.0],
    }), ARQUIVO_CUSTOS)
    salvar_horas(pd.DataFrame({
        "c_custo": [PROJETO_TESTE], "nome": ["Colaborador Teste"], "periodo": ["01/01/2026"], "hs_nor": [8.0],
    }), ARQUIVO_HORAS)
    salvar_orcamento(
        projeto=PROJETO_TESTE, orcamento_previsto=1000.0, status_projeto="Viabilizado",
        data_inicio=None, prev_viabilidade=None, prev_qualidade=None,
        prev_aprov_lancamento=None, prev_lancamento=None, real_viabilidade=None,
        real_qualidade=None, real_aprov_lancamento=None, real_lancamento=None,
    )
    salvar_previsao_periodo(PROJETO_TESTE, "2026", 1000.0, "anual")


def test_deletar_projeto_completo_remove_tudo_do_projeto():
    _popular_projeto_teste()
    resultado = deletar_projeto_completo(PROJETO_TESTE)
    assert resultado["custos"] == 1
    assert resultado["horas"] == 1
    assert resultado["orcamento"] == 1

    assert carregar_orcamento_projeto(PROJETO_TESTE) is None
    assert carregar_previsoes_projeto(PROJETO_TESTE).empty
    assert (carregar_custos()["centro_de_custo"] == PROJETO_TESTE).sum() == 0
    assert (carregar_horas()["c_custo"] == PROJETO_TESTE).sum() == 0


def test_limpar_tudo_esvazia_todas_as_tabelas():
    # ATENCAO: limpar_tudo() apaga TODAS as linhas das 4 tabelas, não só as
    # de teste. Só execute este teste contra um banco Supabase dedicado ao
    # desenvolvimento deste app, sem dados de produção reais.
    _popular_projeto_teste()
    limpar_tudo()
    assert carregar_custos().empty
    assert carregar_horas().empty
    assert carregar_previsoes_projeto(PROJETO_TESTE).empty
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd dashboard_projetos && pytest tests/test_db_delecao.py -v`
Expected: FAIL — `ImportError: cannot import name 'deletar_projeto_completo'`.

- [ ] **Step 3: Implementar em `utils/db.py`**

Acrescente ao final de `dashboard_projetos/utils/db.py`:

```python

# ─────────────────────────────────────────────────────
# Deleção em massa
# ─────────────────────────────────────────────────────

def deletar_projeto_completo(projeto: str) -> dict:
    with _engine().begin() as con:
        r_custos = con.execute(
            text("DELETE FROM custos WHERE centro_de_custo = :p"), {"p": projeto}
        ).rowcount
        r_horas = con.execute(
            text("DELETE FROM horas WHERE c_custo = :p"), {"p": projeto}
        ).rowcount
        r_orc = con.execute(
            text("DELETE FROM orcamentos_cronograma WHERE projeto = :p"), {"p": projeto}
        ).rowcount
        con.execute(text("DELETE FROM previsoes_periodo WHERE projeto = :p"), {"p": projeto})
        con.execute(text("""
            DELETE FROM importacoes
            WHERE tipo = 'custos'
              AND arquivo NOT IN (SELECT DISTINCT arquivo FROM custos)
        """))
        con.execute(text("""
            DELETE FROM importacoes
            WHERE tipo = 'horas'
              AND arquivo NOT IN (SELECT DISTINCT arquivo FROM horas)
        """))
    return {"custos": r_custos, "horas": r_horas, "orcamento": r_orc}


def limpar_tudo() -> None:
    with _engine().begin() as con:
        con.execute(text("DELETE FROM custos"))
        con.execute(text("DELETE FROM horas"))
        con.execute(text("DELETE FROM importacoes"))
        con.execute(text("DELETE FROM previsoes_periodo"))
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd dashboard_projetos && pytest tests/test_db_delecao.py -v`
Expected: PASS nos 2 testes.

- [ ] **Step 5: Rodar a suíte completa**

Run: `cd dashboard_projetos && pytest tests/ -v`
Expected: PASS em todos os testes de `tests/test_db_*.py` (conexão, schema, custos, horas, orçamentos, previsões, deleção).

- [ ] **Step 6: Commit**

```bash
git add dashboard_projetos/utils/db.py dashboard_projetos/tests/test_db_delecao.py
git commit -m "feat: implementa delecao em massa na camada Postgres"
```

---

### Task 8: Validação manual end-to-end e configuração em produção

**Files:**
- Nenhum arquivo novo — esta task é validação manual do app completo e configuração de produção.

**Interfaces:**
- Consumes: todas as funções de `utils/db.py` (Tasks 1–7), via `app.py` e `pages/*.py` (sem modificação).

- [ ] **Step 1: Subir o app localmente**

Run: `cd dashboard_projetos && streamlit run app.py`
Expected: app abre no navegador, tela de login aparece (usando `AUTH_USERS` já configurado em `.streamlit/secrets.toml`).

- [ ] **Step 2: Testar upload de planilhas**

Login como admin → página **Upload de Arquivos** → enviar uma planilha de teste de custos e uma de horas (pode ser uma cópia pequena do formato mostrado em "Ver formato esperado das planilhas"). Confirmar mensagem de sucesso e que a aba **Dashboard Financeiro** mostra os dados.

- [ ] **Step 3: Testar orçamento e cronograma**

Página **Orçamentos** → selecionar o projeto importado → preencher orçamento, status e ao menos uma data de marco → salvar. Confirmar que o resumo abaixo do formulário reflete os valores salvos.

- [ ] **Step 4: Testar previsão por período**

Na mesma página, em **Previsões Orçamentárias por Período** → adicionar uma previsão → confirmar que aparece na tabela.

- [ ] **Step 5: Reiniciar o processo (simula um redeploy) e confirmar persistência**

Pare o `streamlit run` (Ctrl+C) e rode de novo:

Run: `cd dashboard_projetos && streamlit run app.py`
Expected: após login, os dados de custos, horas, orçamento, status, cronograma e previsão cadastrados nos Steps 2–4 continuam todos presentes — esta é a prova de que a persistência não depende mais do disco do container.

- [ ] **Step 6: Testar fluxo de visualizador**

Logout → entrar com um usuário de perfil `visualizador` (de `AUTH_USERS`) → confirmar que upload, edição de orçamento e exclusões estão desabilitados, mas os dados são visíveis.

- [ ] **Step 7: Testar exclusões**

Como admin: excluir a importação de teste (página Upload → remover por arquivo), excluir o projeto de teste completo (página Orçamentos → "Excluir todos os dados deste projeto" com confirmação `EXCLUIR`). Confirmar que os dados somem do dashboard.

- [ ] **Step 8: Configurar produção**

No painel do Streamlit Community Cloud do app: **Manage app → Settings → Secrets**, adicionar a linha `DATABASE_URL = "..."` (a mesma connection string usada localmente, ou uma equivalente do mesmo projeto Supabase) junto ao `AUTH_USERS` já configurado.

- [ ] **Step 9: Deploy e smoke test em produção**

Run: `git push`
Expected: Streamlit Cloud redeploya automaticamente. Após o redeploy, abrir o app publicado, logar, e repetir rapidamente os Steps 2–3 (upload + orçamento) para confirmar que grava no Postgres de produção. Repetir o Step 5 (forçar um redeploy manual pelo painel "Reboot app") e confirmar que os dados sobrevivem — validação final de que o problema original foi resolvido.

---

## Self-Review

- **Cobertura da spec:** todas as funções públicas listadas na spec (`init_db`, `migrar_db`, `salvar_custos`, `salvar_horas`, `salvar_orcamento`, `salvar_previsao_periodo`, `deletar_previsao_periodo`, `carregar_previsoes_projeto`, `carregar_todas_previsoes`, `carregar_custos`, `carregar_horas`, `carregar_orcamentos`, `carregar_orcamento_projeto`, `listar_importacoes`, `deletar_importacao`, `deletar_orcamento_projeto`, `deletar_projeto_completo`, `limpar_tudo`) têm uma task que as implementa e testa. Remoção do `auto-commit.yml` está na Task 1. Atualização de `.env.example`/`secrets.toml.example` está na Task 1. Validação end-to-end e deploy em produção estão na Task 8.
- **Placeholders:** nenhum "TBD"/"implementar depois" — todo passo tem código completo ou comando exato com resultado esperado.
- **Consistência de tipos:** `carregar_orcamento_projeto` retorna `dict | None` em todas as referências; `salvar_custos`/`salvar_horas` retornam `tuple[int, bool]` consistentemente; `deletar_projeto_completo` retorna `dict` com as mesmas três chaves (`custos`, `horas`, `orcamento`) usadas pela página `0_orcamento.py` hoje.
- **Fora de escopo, propositalmente:** redesign de filtros, melhorias de upload/download e de exibição (identificados na avaliação geral) não fazem parte deste plano.
