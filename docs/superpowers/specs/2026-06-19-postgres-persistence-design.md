# Migração de persistência: SQLite local → Postgres (Supabase)

Data: 2026-06-19
Status: Aprovado para implementação

## Contexto e problema

O dashboard (`dashboard_projetos/`) é um app Streamlit hospedado no Streamlit Community
Cloud. Hoje a persistência é feita por um arquivo SQLite local
(`dashboard_projetos/data/dashboard.db`), criado em runtime e listado no
`.gitignore`.

O Streamlit Community Cloud usa armazenamento **efêmero**: qualquer arquivo que não
veio do repositório Git é perdido a cada reboot/redeploy do container. Como o
`.db` nunca é versionado, **todo dado cadastrado (custos, horas, orçamentos,
cronogramas) pode ser perdido a qualquer redeploy** — incluindo redeploys
disparados automaticamente por novos commits no repositório.

Reforça esse risco o workflow `.github/workflows/auto-commit.yml`, que cria um
commit vazio a cada 4 horas. Push para o repo dispara redeploy automático no
Streamlit Cloud, então esse workflow pode estar causando (ou ajudando a causar)
perda periódica de dados, sem benefício real.

Inspeção de um `dashboard.db` remanescente de uma versão anterior do projeto
(`OLDdashboard_projetosV2/data/dashboard.db`) confirmou que não há dados reais
hoje — todas as tabelas estão vazias. Não há, portanto, necessidade de migrar
dados existentes: a implementação parte do zero.

## Decisão

Substituir completamente o SQLite por um banco Postgres gerenciado no
**Supabase** (novo projeto, provisionado especificamente para este app). Não
haverá fallback para SQLite — local e produção usam o mesmo Postgres. Essa
decisão prioriza simplicidade (um único dialeto SQL para manter) sobre a
flexibilidade de rodar 100% offline.

## Por que isso é seguro de isolar

`dashboard_projetos/utils/db.py` é a única camada que fala com o banco. Todos
os outros módulos (`data_processor.py`, `pages/0_orcamento.py`,
`pages/1_upload.py`, `pages/2_dashboard.py`, `pages/3_projetos.py`, `app.py`)
só importam funções públicas de `db.py` (`carregar_custos()`,
`salvar_orcamento()`, `agregar_tudo()` via `data_processor.py`, etc.) e
recebem `pandas.DataFrame`/`dict` de volta — nunca SQL ou tipos específicos do
driver. A migração fica contida em `db.py`; nenhuma página precisa mudar.

## Design técnico

### Cliente de banco

SQLAlchemy (`create_engine`) + driver `psycopg2-binary`. Não usar o cliente
REST `supabase-py`: `db.py` já é construído em torno de SQL bruto e
`pandas.read_sql` / `DataFrame.to_sql`, e a sintaxe de upsert
(`INSERT ... ON CONFLICT (...) DO UPDATE SET col = excluded.col`) já é
idêntica entre SQLite e Postgres — manter SQL bruto com um Engine SQLAlchemy é
a menor mudança de superfície possível.

### Conexão

Hoje cada função abre um `sqlite3.connect()` novo (arquivo local, latência
desprezível). Postgres remoto tem latência de rede por chamada, então a nova
`_conn()` não abre uma conexão nova a cada vez: um único `Engine` SQLAlchemy é
criado uma vez por processo via `st.cache_resource` e reutilizado (pool de
conexões) entre os reruns do Streamlit.

### Credenciais

Nova secret `DATABASE_URL` (connection string Postgres do Supabase), lida pelo
mesmo padrão já usado em `utils/auth.py` para `AUTH_USERS`: `st.secrets`
primeiro (produção), variável de ambiente como alternativa local. Documentar
em `.env.example` e `.streamlit/secrets.toml.example`.

### Tradução de schema (SQLite → Postgres)

| Item SQLite | Equivalente Postgres |
|---|---|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `GENERATED ALWAYS AS IDENTITY` |
| `PRAGMA table_info(tabela)` (migração de colunas) | `SELECT column_name FROM information_schema.columns WHERE table_name = %s` |
| `PRAGMA journal_mode=WAL` / `synchronous` / `foreign_keys` | removidos (não aplicável) |
| Placeholders `?` | Placeholders `%s` |
| `datetime('now','localtime')` como default de coluna | Timestamp gerado em Python (`datetime.now().strftime("%Y-%m-%d %H:%M:%S")`) e passado como parâmetro |

Colunas de data de cronograma (`data_inicio`, `prev_*`, `real_*`) permanecem
**TEXT** no formato `YYYY-MM-DD`, exatamente como hoje. Isso preserva sem
alterações toda a lógica de parsing já espalhada pelas páginas
(`_parse_date_or_none`, slices `[:10]`, comparações de string), evitando que o
driver Postgres devolva objetos `datetime`/`date` onde o código espera string.

A sintaxe de upsert (`ON CONFLICT ... DO UPDATE SET ... = excluded.col`),
`UNIQUE(...)` em `CREATE TABLE`, e `CREATE TABLE IF NOT EXISTS` são idênticas
entre os dois bancos — sem mudança de lógica nessas partes.

### Interface pública mantida (sem mudança nos consumidores)

Todas as funções abaixo mantêm assinatura e tipo de retorno:
`init_db`, `migrar_db`, `salvar_custos`, `salvar_horas`, `salvar_orcamento`,
`salvar_previsao_periodo`, `deletar_previsao_periodo`,
`carregar_previsoes_projeto`, `carregar_todas_previsoes`, `carregar_custos`,
`carregar_horas`, `carregar_orcamentos`, `carregar_orcamento_projeto`,
`listar_importacoes`, `deletar_importacao`, `deletar_orcamento_projeto`,
`deletar_projeto_completo`, `limpar_tudo`.

### Limpeza incluída neste trabalho

- Remover `.github/workflows/auto-commit.yml` — sem função depois da
  migração, e era risco de redeploy/perda de dados.
- Atualizar `requirements.txt`: adicionar `sqlalchemy` e `psycopg2-binary`.

### Fora de escopo (não faz parte desta mudança)

- Redesign dos filtros (cascata, filtro por área/filial/segmento).
- Melhorias de upload/download (multi-upload, dedup por conteúdo, templates).
- Melhorias de exibição (ordenação por risco, drill-through de alertas).

Esses itens foram identificados na avaliação geral do projeto e ficam para
trabalho futuro, fora desta migração de persistência.

## Validação

Sem dados reais em produção hoje, o corte é direto — sem dual-write, sem
feature flag (YAGNI). Plano de teste manual pós-migração:

1. Subir o app local apontando para o Supabase novo.
2. Importar uma planilha de teste de custos e de horas.
3. Cadastrar orçamento, status e cronograma de um projeto.
4. Cadastrar uma previsão por período.
5. **Reiniciar o processo Streamlit local** (simula um redeploy) e confirmar
   que todos os dados acima continuam presentes.
6. Testar fluxo de visualizador (somente leitura) vs. admin.
7. Testar exclusão de uma importação por arquivo, exclusão de projeto
   completo, e "apagar tudo".
8. Deploy em produção: configurar `DATABASE_URL` nos Secrets do Streamlit
   Cloud e confirmar que o app publicado lê/grava no mesmo Postgres.
