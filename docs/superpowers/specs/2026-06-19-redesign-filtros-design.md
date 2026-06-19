# Redesign dos filtros (Dashboard / Andamento dos Projetos)

## Problema

As páginas **Dashboard Financeiro** (`pages/2_dashboard.py`) e **Andamento dos
Projetos** (`pages/3_projetos.py`) têm um bloco de filtros na sidebar
duplicado byte-a-byte: quatro `st.multiselect` (Projetos, Ano, Mês, Status do
Projeto) + botão "Limpar filtros", compartilhando as mesmas chaves de
`st.session_state` entre as duas páginas.

Hoje os filtros `Projetos` e `Mês` começam com **todas as opções já
marcadas**. Com 20 a 100 projetos cadastrados, isso produz uma parede de
etiquetas ("pills") — uma por projeto — que ocupa toda a sidebar antes mesmo
do campo de busca ficar visível. Isso torna difícil tanto isolar um projeto
específico quanto montar/ajustar um grupo de projetos para comparação — os
dois usos reais que o usuário faz do filtro.

Os filtros `Ano` e `Status do Projeto` já não sofrem disso: usam defaults
"curados" (ano corrente; status não-terminais) que tipicamente selecionam
poucos itens.

## Decisão

Adotar uma convenção única nos 4 filtros: **seleção vazia = sem filtro
(mostra tudo)**. Isso já é como `Ano` e `Status` funcionam internamente hoje
(a aplicação do filtro só ocorre `if selecionados:`); o problema é apenas o
*default inicial* de `Projetos` e `Mês`, que hoje preenche a seleção com a
lista inteira em vez de deixá-la vazia.

Mudanças de comportamento:

- `Projetos` e `Mês` passam a iniciar **vazios** (sem pills) em vez de
  "todos marcados". `Ano` e `Status` mantêm seus defaults curados (ano
  corrente / status ativos) no primeiro carregamento da sessão.
- O botão **"Limpar filtros"** zera os 4 filtros (`[]`) em vez de marcar
  explicitamente todos os valores — mesmo efeito visual (mostra tudo), sem
  popular pills.
- Cada multiselect ganha uma legenda (`st.caption`) indicando quantos itens
  estão sendo considerados: `"N de TOTAL selecionados"` quando há seleção,
  ou `"Mostrando todos os TOTAL"` quando vazio. Isso compensa a ausência
  de pills como sinal visual de "quantos itens estão no filtro".

## Arquitetura

O bloco de filtros (hoje duplicado em `pages/2_dashboard.py` e
`pages/3_projetos.py`) é extraído para duas funções novas em
`utils/data_processor.py`, ao lado dos helpers de UI já existentes para
essas páginas (`render_selo_dados`, `render_faixa_alertas`):

- **`aplicar_filtros(df, df_custos_raw, projetos_sel, anos_sel, meses_sel, status_sel) -> pd.DataFrame`**
  Lógica pura de filtragem (sem widgets Streamlit), replicando exatamente a
  lógica hoje duplicada nas duas páginas: filtra por `nome_projeto`
  (Projetos), por `centro_de_custo` via `df_custos_raw` (Ano, Mês) e por
  `status_projeto` (Status). Seleção vazia em qualquer critério = não
  filtra por esse critério.

- **`render_filtros_sidebar(df, df_custos_raw) -> pd.DataFrame`**
  Desenha a sidebar: calcula as listas de opções, inicializa/normaliza
  `st.session_state` (defaults vazios para Projetos/Mês, curados para
  Ano/Status), renderiza os 4 `st.multiselect` + legendas + botão "Limpar
  filtros", e por fim chama `aplicar_filtros(...)` com as seleções atuais,
  retornando o resultado.

Cada página (`2_dashboard.py`, `3_projetos.py`) passa a chamar apenas:

```python
df_f = render_filtros_sidebar(df_dashboard, df_custos_raw)
```

eliminando a duplicação. O restante de cada página (cálculo de `df_c_f`,
`df_h_f`, etc.) continua como está hoje, a partir de `df_f`.

## Testes

- `aplicar_filtros` é testável com pytest puro (DataFrames simples, sem
  Streamlit). Casos a cobrir: todas as seleções vazias retorna o df
  original; cada critério filtra isoladamente; combinação de múltiplos
  critérios aplica AND entre eles.
- `render_filtros_sidebar` é renderização de widgets — não é testada via
  pytest. Validação manual no navegador local: abrir Dashboard e Andamento
  dos Projetos, confirmar que os multiselects de Projetos/Mês iniciam sem
  pills, que as legendas aparecem corretamente, que digitar no campo de
  busca do multiselect funciona normalmente, e que aplicar/limpar filtros
  produz os mesmos resultados de antes.

## Fora de escopo

- O seletor de projeto único (`st.selectbox`) na página Orçamentos — não
  sofre do problema de "parede de pills" (é seleção única).
- Mudanças de layout, posição ou largura da sidebar.
- Os filtros de `Ano`/`Status` em si (já funcionam bem); só a convenção de
  "vazio = sem filtro" é unificada entre os 4.
