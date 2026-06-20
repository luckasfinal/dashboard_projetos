# Visão Executiva — portfólio de risco combinado (custo + prazo)

## Problema

Uma análise do código atual revelou que a única previsão de "vai estourar o
orçamento" (`projecao_burn_rate`, em `utils/data_processor.py`) só é
exibida na aba "Detalhamento" de `pages/3_projetos.py`, depois de
selecionar manualmente UM projeto. Não existe nenhuma visão de portfólio
que mostre, de uma só vez, quais projetos estão em risco de custo e/ou de
prazo — exatamente o tipo de previsão de problemas que um gerente de
negócios precisa para decisão rápida.

Outras lacunas identificadas na mesma análise:
- A detecção de atraso (`detectar_excecoes`) só verifica o marco final
  (Lançamento); atrasos em Viabilidade/Qualidade/Aprovação não geram
  nenhum alerta de portfólio.
- Três limiares de "% de orçamento preocupante" diferentes coexistem no
  código (`cor_status`: 90/100; `rotulo_consumo`: 80/100; tabela do
  Dashboard: 70/90/100), gerando cores contraditórias para o mesmo número
  em telas diferentes.
- Custo (Dashboard Financeiro) e prazo (Andamento dos Projetos) vivem em
  páginas separadas, nunca cruzados num indicador único por projeto.

## Decisão

Criar uma página nova, **"Visão Executiva"**, dedicada a uma visão de
portfólio ordenada por risco combinado (custo + prazo), pensada para
varredura rápida por gerentes de negócio. Não altera as páginas
existentes (Dashboard Financeiro, Andamento dos Projetos) nem os
limiares que elas já usam — o cálculo de risco desta página é uma lógica
nova e isolada, para não alterar o comportamento de telas já em uso.

### Classificação de risco por projeto

**Risco de custo** — usa a projeção de gasto final já existente
(`projecao_burn_rate`): projeção `< 80%` do orçamento = saudável,
`80–100%` = atenção, `> 100%` = estouro. Para projetos com
`status == "concluido"` (já lançados), usa o `% realizado` final em vez
da projeção. Para projetos com `status == "sem_dados"` (sem histórico de
custo suficiente para calcular ritmo), risco de custo é "indeterminado"
(tratado como saudável para fins de classificação, mas sinalizado nos
motivos como "dados insuficientes para projeção").

**Risco de prazo** — estende a verificação de atraso para os 4 marcos do
cronograma (`prev_viabilidade`/`real_viabilidade`,
`prev_qualidade`/`real_qualidade`,
`prev_aprov_lancamento`/`real_aprov_lancamento`,
`prev_lancamento`/`real_lancamento`). Mesma regra já usada em
`detectar_excecoes` para Lançamento, generalizada: marco está atrasado se
`real` existe e é depois de `prev` (atraso já consumado), OU `real` não
existe e hoje é depois de `prev` (atraso em andamento). Qualquer marco
atrasado (`> 0` dias) conta como risco de prazo, sem tolerância.

**Risco combinado** (nível único por projeto):
- 🔴 **Alto**: risco de custo = estouro, OU pelo menos um marco atrasado.
- 🟡 **Médio**: risco de custo = atenção E nenhum marco atrasado.
- 🟢 **Baixo**: risco de custo = saudável E nenhum marco atrasado.

Cada projeto recebe também uma lista de **motivos** em texto (ex.:
`"Projeção de custo: 118% do orçamento"`, `"Qualidade atrasada 5 dias"`),
concatenando todos os fatores que geraram o nível de risco — não apenas
o primeiro encontrado.

## Conteúdo da página

1. **Filtros**: reaproveita `render_filtros_sidebar` (mesmo componente das
   outras duas páginas) — consistência entre páginas, sem lógica nova de
   filtro.
2. **Resumo no topo**: três contadores (🔴 Alto / 🟡 Médio / 🟢 Baixo),
   visualmente no mesmo estilo de `render_faixa_alertas`.
3. **Cards de risco**: um card por projeto, apenas para os níveis
   **Alto** e **Médio**, ordenados com Alto primeiro (e, dentro de cada
   nível, por `pct_projetado` decrescente). Cada card mostra: nome do
   projeto, badge de nível de risco, lista de motivos, % projetado e
   orçamento.
4. **Baixo risco**: não recebe cards — fica resumido num
   `st.expander` com uma lista compacta (uma linha por projeto), para
   manter a página curta quando a maioria dos projetos está saudável.
5. **Exportação**: botão de download CSV com a tabela completa
   (todos os níveis, todas as colunas de risco). Sem exportação em PDF
   nesta primeira versão.

## Arquitetura

- **`calcular_risco_portfolio(df: pd.DataFrame, df_custos_raw: pd.DataFrame) -> pd.DataFrame`**
  em `utils/data_processor.py` — função pura (sem widgets Streamlit),
  testável via pytest. Recebe o mesmo `df` agregado por projeto (saída de
  `agregar_tudo`/`aplicar_filtros`) e `df_custos_raw`. Para cada projeto,
  reaproveita `projecao_burn_rate` (cálculo de custo) e implementa a
  verificação de atraso nos 4 marcos (cálculo de prazo) para determinar o
  nível de risco. Retorna um DataFrame com colunas: `projeto`,
  `nome_projeto`, `nivel_risco` (`"alto"`/`"medio"`/`"baixo"`), `motivos`
  (lista de strings), `pct_projetado`, `dias_atraso_max`.

- **`pages/4_visao_executiva.py`** — página nova. Estrutura: filtros →
  `calcular_risco_portfolio` → resumo (contadores) → cards (Alto/Médio) →
  expander (Baixo) → exportação CSV. Segue o mesmo padrão de
  organização das páginas existentes (`init_db()`, `agregar_tudo()`,
  `render_filtros_sidebar`, etc.).

## Testes

- `calcular_risco_portfolio` é testável com pytest puro (DataFrames
  simples, sem Streamlit), seguindo o padrão de `aplicar_filtros`. Casos
  a cobrir: projeto saudável (baixo risco); projeto com projeção de
  custo entre 80–100% e sem atraso (médio risco); projeto com projeção
  acima de 100% (alto risco, motivo de custo); projeto com algum marco
  atrasado mas custo saudável (alto risco, motivo de prazo); projeto com
  ambos os problemas (alto risco, dois motivos); projeto concluído
  (usa % realizado, não projeção); projeto sem dados de custo
  suficientes (risco de custo indeterminado/saudável, motivo informativo).
- A página em si (`pages/4_visao_executiva.py`) não é testada via pytest
  (renderização de widgets) — validação manual no navegador: confirmar
  contadores corretos, cards só para Alto/Médio, ordenação por risco,
  expander de Baixo risco, exportação CSV funcionando.

## Fora de escopo

- Unificar os limiares inconsistentes já usados em `cor_status`,
  `rotulo_consumo` e na tabela do Dashboard Financeiro — fica como
  melhoria futura, documentada mas não resolvida nesta rodada (evita
  alterar comportamento de telas já em uso, sem ter sido pedido).
- Integrar a funcionalidade "Previsão por Período" (hoje sem nenhuma
  tela que a exiba) — decisão futura.
- Exportação em PDF para a Visão Executiva.
- Qualquer alteração nas páginas Dashboard Financeiro ou Andamento dos
  Projetos.
