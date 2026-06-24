# Dashboard Executivo de Projetos — Design Spec

**Data:** 2026-06-24  
**Branch de implementação:** `feat/dashboard-executivo`  
**Rota Streamlit:** determinada pelo nome do arquivo (`5_dashboard_executivo.py`)  
**Acesso:** todos os usuários autenticados (admin + visualizador)

---

## 1. Contexto e motivação

O sistema já possui três páginas analíticas (Dashboard Financeiro, Andamento dos Projetos, Visão Executiva), mas nenhuma delas consolida em um único lugar as dimensões de prazo, custo, recursos e forecast para consumo executivo rápido pela diretoria. Esta página preenche essa lacuna sem alterar as páginas existentes.

---

## 2. Arquivos impactados

### Criados
| Arquivo | Responsabilidade |
|---|---|
| `dashboard_projetos/utils/dashboard_executivo.py` | Toda lógica de negócio nova: categorização de contas, cálculo de marcos, burn rate, forecasts, EAC, matriz |
| `dashboard_projetos/pages/5_dashboard_executivo.py` | Página Streamlit — orquestra dados, filtros e visualizações |
| `dashboard_projetos/tests/test_dashboard_executivo.py` | Testes unitários das funções de cálculo |

### Alterados
| Arquivo | O que muda |
|---|---|
| `dashboard_projetos/utils/charts.py` | +5 funções de gráfico: barras horizontais, barras empilhadas, donut, série temporal, scatter de quadrantes |
| `dashboard_projetos/app.py` | +1 entrada no menu "📊 Análises": `5_dashboard_executivo.py` com ícone `📋` e título "Dashboard Executivo" |

### Intocados
`data_processor.py`, `db.py`, `auth.py`, páginas existentes — nenhuma alteração.

---

## 3. Fluxo de dados

```
db.py ──► data_processor.agregar_tudo()
              │
              ▼
     (df_merged, df_custos_raw, df_horas_raw)
              │
              ▼
   dashboard_executivo.py (cálculos puros)
   ├── categorizar_conta(conta) → str
   ├── calcular_resumo_executivo() → dict
   ├── calcular_status_projetos() → DataFrame
   ├── calcular_marcos() → DataFrame
   ├── calcular_custos_por_categoria() → DataFrame
   ├── calcular_recursos() → DataFrame
   ├── calcular_burn_rate() → DataFrame
   ├── calcular_forecast_prazo() → DataFrame
   ├── calcular_forecast_custo() → DataFrame
   └── calcular_matriz_prazo_custo() → DataFrame
              │
              ▼
   charts.py (figuras Plotly) + 5_dashboard_executivo.py (layout Streamlit)
```

`agregar_tudo()` já é cacheada com `@st.cache_data(ttl=5)` — sem chamadas extras ao banco nas novas funções.

---

## 4. Filtros

### Filtros compartilhados (reutilizados)
`render_filtros_sidebar()` de `data_processor.py` — mantém as mesmas chaves de `session_state` (`filtro_projetos`, `filtro_anos`, `filtro_meses`, `filtro_status`). Ao navegar para esta página, os filtros já aplicados nas outras páginas são preservados.

### Filtros exclusivos da página
Renderizados na sidebar abaixo dos filtros globais, com chaves próprias:

| Chave session_state | Widget | Opções |
|---|---|---|
| `exec_filtro_categoria_custo` | multiselect "Categoria de Custo" | Mão de obra, Terceiros, Materiais, Viagens, Outras |
| `exec_filtro_colaborador` | multiselect "Colaborador" | nomes únicos de `df_horas_raw["nome"]` filtrado pelos projetos selecionados |

---

## 5. Categorização de contas (`dashboard_executivo.py`)

O campo `conta` na tabela `custos` contém código numérico + descrição textual (ex: `"610000 - Mão de Obra Própria"`). A função `categorizar_conta(conta: str) -> str` faz matching case-insensitive por palavras-chave na descrição:

```python
PALAVRAS_CATEGORIA = {
    "Mão de obra":  ["mão de obra", "salario", "salário", "pessoal", "folha", "rh"],
    "Terceiros":    ["terceiro", "serviço", "servico", "contratado", "consultoria", "fornecedor"],
    "Materiais":    ["material", "componente", "insumo", "peça", "peca", "estoque"],
    "Viagens":      ["viagem", "hospedagem", "transporte", "diária", "diaria", "deslocamento"],
}
# fallback: "Outras"
```

Este dict é configurável — ajuste conforme os códigos contábeis reais do sistema.

---

## 6. Cálculo de marcos e % concluído

Os 4 marcos fixos do banco com seus **pesos de progresso**:

| Coluna (prev / real) | Marco | Peso |
|---|---|---|
| `prev_viabilidade` / `real_viabilidade` | Viabilidade | 45% |
| `prev_qualidade` / `real_qualidade` | Qualidade | 40% |
| `prev_aprov_lancamento` / `real_aprov_lancamento` | Aprovação para Lançamento | 5% |
| `prev_lancamento` / `real_lancamento` | Lançamento | 10% |

**`pct_concluido`** = soma dos pesos dos marcos com `real_*` preenchido.  
**`status_marco`**: `"Concluído"` / `"Atrasado"` / `"No prazo"` / `"Pendente"`.  
**Desvio** = `(data_realizada - data_prevista).days` (positivo = atraso, negativo = adiantado).

---

## 7. Seções da página

### Seção 1 — Resumo Executivo (KPI cards)
6 métricas em cards `st.metric`:
- Projetos ativos (status não terminal)
- Projetos com atraso (ao menos 1 marco realizado após data prevista)
- Horas consumidas (total `hs_nor` filtrado)
- Custos acumulados (total `realizado` filtrado)
- % médio de conclusão (média de `pct_concluido` entre projetos filtrados)
- Prazo médio de atraso (média de desvio positivo dos marcos concluídos)

### Seção 2 — Status Geral dos Projetos (tabela)
Colunas: Projeto | % Concluído | Marcos Concluídos | Marcos Totais (4) | Atraso Médio (dias) | Horas | Custo | Status visual.

Status visual via badge HTML (padrão `badge_status_projeto()`):
- 🟢 Verde: atraso médio ≤ 0
- 🟡 Amarelo: atraso entre 1–30 dias
- 🔴 Vermelho: atraso > 30 dias

Permite ordenação e busca via `st.dataframe`.

### Seção 3 — Evolução Física (gráfico barras horizontais)
`grafico_evolucao_fisica(df)` em `charts.py`. Barras horizontais por projeto, comprimento = `pct_concluido`. Ao clicar, expande tabela dos 4 marcos do projeto (drill-down via `st.expander`).

### Seção 4 — Análise de Marcos (tabela)
`calcular_marcos(df)` retorna DataFrame com uma linha por marco por projeto. Colunas: Projeto | Marco | Data Prevista | Data Realizada | Desvio (dias). Colorização por linha: verde/amarelo/vermelho conforme desvio. Métricas acima da tabela: total de marcos, marcos atrasados, % atrasados.

### Seção 5 — Custos por Projeto (barras empilhadas)
`grafico_custos_empilhados(df_cat)` em `charts.py`. Agrupa `(projeto, categoria_custo)`, plota barras verticais empilhadas. Cores fixas por categoria (consistentes com seção 6). Hover mostra valor absoluto + % da categoria no projeto.

### Seção 6 — Distribuição de Custos (donut)
`grafico_distribuicao_custos(df_cat)` em `charts.py`. Agrega total por categoria nos projetos filtrados. Hover mostra valor absoluto + %.

### Seção 7 — Consumo de Recursos (tabela + rankings)
Tabela: Projeto | Horas Totais | Colaboradores | Horas/Colaborador.  
Abaixo: dois `st.columns` com rankings Top 5 projetos (mais horas) e Top 5 colaboradores (mais horas apontadas).

### Seção 8 — Burn Rate (gráfico temporal)
`burn_rate = custo_acumulado_mensal / n_meses_decorridos` por projeto.  
`grafico_burn_rate(df_br)`: linha temporal do gasto mensal acumulado por projeto. Anotação do ritmo médio mensal por projeto no hover.

### Seção 9 — Forecast de Prazo (tabela)
`calcular_forecast_prazo(df_marcos)`: para cada projeto, calcula atraso médio dos marcos concluídos e projeta o término do Lançamento.  
Colunas: Projeto | Data Planejada (Lançamento) | Forecast | Desvio.  
Destacar em vermelho projetos com Forecast > Data Planejada.

### Seção 10 — Forecast de Custo / EAC (tabela)
`EAC = custo_atual / pct_concluido` (onde `pct_concluido > 0`).  
Colunas: Projeto | Custo Atual | % Concluído | EAC | Orçamento | Desvio EAC vs Orçamento.  
Destaque vermelho quando `EAC > orcamento_previsto`. Projetos com `pct_concluido == 0` mostram "—".

### Seção 11 — Matriz Executiva Prazo × Custo (scatter)
`grafico_matriz_executiva(df_matriz)` em `charts.py`.  
Eixo X = desvio de prazo médio (dias). Eixo Y = `(EAC / orcamento - 1) * 100` (desvio % de custo).  
Linhas de referência em x=0 e y=0 dividem em 4 quadrantes:

| Quadrante | Condição | Cor |
|---|---|---|
| Controlado | x ≤ 0 e y ≤ 0 | 🟢 verde |
| Risco de Prazo | x > 0 e y ≤ 0 | 🟡 amarelo |
| Risco de Custo | x ≤ 0 e y > 0 | 🟠 laranja |
| Crítico | x > 0 e y > 0 | 🔴 vermelho |

*Nota: complementar ao scatter da Visão Executiva. Aquele usa projeção de custo × atraso máximo; este usa desvio de EAC × desvio médio de prazo.*

---

## 8. Testes (`test_dashboard_executivo.py`)

| Função | Casos cobertos |
|---|---|
| `categorizar_conta()` | keyword conhecida, fallback "Outras", string vazia, case-insensitive |
| `calcular_marcos()` — pesos | 0 marcos = 0%, todos = 100%, pesos parciais corretos (ex: só viabilidade = 45%) |
| `calcular_marcos()` — status | marco sem data = Pendente, real > prev = Atrasado, real ≤ prev = Concluído no prazo |
| `calcular_forecast_prazo()` | atraso médio com mix adiantado/atrasado, projeto sem data de lançamento |
| `calcular_forecast_custo()` | EAC com pct > 0, divisão por zero quando pct = 0 retorna None |
| `calcular_burn_rate()` | ritmo com 1 mês, com vários meses, projeto sem histórico retorna 0 |

---

## 9. Riscos técnicos

| Risco | Mitigação |
|---|---|
| Dict de categorização impreciso na primeira versão | Seção 6 (donut) expõe "Outras" dominante como sinal de ajuste; dict é configurável sem mudar lógica |
| Projetos sem marcos cadastrados | Seções 9 e 10 mostram "—" por linha; cards da seção 1 excluem esses projetos das médias |
| Performance com muitos projetos | `agregar_tudo()` cacheada; funções de cálculo operam em memória; `LIMITE_GRAFICO = 20` de `charts.py` aplicado nos gráficos de barras |
| Sobreposição visual com Visão Executiva | Páginas têm enfoques distintos; documentado aqui para referência futura |

---

## 10. Workflow de entrega

1. Implementar em branch `feat/dashboard-executivo`
2. Usuário avalia em localhost
3. Aprovação → merge na `main` → deploy Streamlit Cloud
