# P8: guia de montagem do dashboard no Power BI Desktop

Resultado esperado: um relatório de 8 páginas sobre as avaliações P7, P7b e P7c, com ROI e intervalos de confiança, separação por **classe de campo** (explorável × agressivo × adaptativo × self-play), posição, stack, decisões, versões e auditoria.

> Este guia e os arquivos desta pasta foram gerados e testados fora do Power BI. A exportação é validada por testes automáticos e por reconciliação. A **montagem visual** é feita por você no Power BI Desktop, seguindo os passos abaixo, e nenhum `.pbix` é distribuído.

Arquivos desta pasta:

| Arquivo | Uso |
|---|---|
| `PowerQuery.m` | Parâmetro, função de carga e consultas (uma por tabela) |
| `measures.dax` | As 49 medidas, comentadas (fonte única) |
| `measures_dax_query_view.dax` | As mesmas medidas num bloco `DEFINE`, para criar todas de uma vez |
| `theme_poker_lab.json` | Tema (paleta validada para daltonismo, fundo claro) |
| `POWERBI_MODEL_SPEC_P8.md` | Especificação do modelo |

---

## Passo 0: obter os dados
Os dados vêm de `poker-lab export powerbi`, que gera a pasta com um subdiretório por tabela, `manifest.json` e `reconciliation.json`. A exportação só é publicada se **todos** os KPIs reconciliarem (SQL × arquivos × relatório congelado).

Se você recebeu a pasta pronta (`poker-powerbi`), pule para o passo 1.

## Passo 1: carregar as tabelas (≈10 min)
1. Abra o Power BI Desktop. Vá em **Página Inicial → Transformar dados**.
2. **Gerenciar parâmetros → Novo**:
   - nome: `PastaExportacao`;
   - tipo: Texto;
   - valor: o caminho da pasta, por exemplo `C:\Users\PlayHard\Downloads\poker-powerbi`.
3. **Nova fonte → Consulta nula → Editor avançado**. Cole a função de `PowerQuery.m` (seção 2) e renomeie a consulta para `fnCarregarTabela`.
4. Para cada tabela da lista (seção 3 de `PowerQuery.m`), crie uma **Consulta nula** com `= fnCarregarTabela("NomeDaTabela")` e dê à consulta o mesmo nome da tabela.

   Atalho: crie uma, duplique e troque só o nome.
5. Clique com o botão direito em `fnCarregarTabela` e em `PastaExportacao` e desmarque **Habilitar carga**.
6. **Fechar e aplicar.**

## Passo 2: relacionamentos (Exibição de modelo)
Todos são **um-para-muitos**, com filtro em **direção única** (da dimensão para o fato). Desative a detecção automática em Arquivo → Opções → Carregamento de dados → "Detectar automaticamente novas relações".

| De (1) | Para (*) |
|---|---|
| `DimRun[RunKey]` | `DimScenario[RunKey]` |
| `DimFieldClass[FieldClass]` | `DimScenario[FieldClass]` |
| `DimScenario[ScenarioKey]` | `FactEntryResult`, `FactHandHero`, `FactDecision`, `FactLedger`, `FactScenarioSummary`, `FactPairedComparison`, `FactBreakdownCI`, `FactAllinLuck`, `FactProgressive`, `FactSteal`, `FactStealByDimension` (coluna `ScenarioKey` em cada) |
| `DimCandidate[CandidateKey]` | as mesmas tabelas de fato (coluna `CandidateKey`) |
| `DimPosition[Position]` | `FactHandHero[Position]` e `FactDecision[Position]` |
| `DimStackBucket[StackBucket]` | `FactHandHero[StackBucket]` |
| `DimPhase[Phase]` | `FactHandHero[Phase]` |
| `DimOpponentProfile[OpponentProfile]` | `FactEntryResult[OpponentProfile]` |

**Não** ligue `DimRun` diretamente aos fatos. O filtro de execução chega aos fatos por `DimScenario`, porque `ScenarioKey` já contém a execução. Ligar `DimRun` também aos fatos criaria caminhos ambíguos.

Ordenação (Ferramentas de coluna → Classificar por coluna):
- `DimPosition[Position]` por `PositionOrder`;
- `DimStackBucket[StackBucket]` por `StackBucketOrder`;
- `DimPhase[Phase]` por `PhaseOrder`;
- `DimFieldClass[FieldClassLabel]` por `FieldClassOrder`.

## Passo 3: medidas (≈2 min)
1. **Página Inicial → Inserir dados**: crie uma tabela vazia chamada `_Medidas` e carregue.
2. Abra a **Exibição de consulta DAX**, cole todo o conteúdo de `measures_dax_query_view.dax` e clique no link **"Atualizar modelo: Adicionar 49 novas medidas"** que aparece acima do `DEFINE`.
3. Formatos:
   - percentual (0,0%): `ROI Agregado`, `ITM %`, `ROI (relatório)`, `ROI IC Inferior`, `ROI IC Superior`, `% Fold`, `% Check/Call`, `% Bet/Raise`, `Showdown %`, `Vitória no Showdown %`, `Taxa de Steal`;
   - decimal com 3 casas: `Diferença Pareada`, `Diferença IC Inferior`, `Diferença IC Superior`, `bb por Mão` e os ICs de bb.
4. Oculte a coluna da tabela `_Medidas`. O Power BI passa a mostrá-la como tabela de medidas.

## Passo 4: tema
**Exibir → Temas → Procurar temas** e escolha `theme_poker_lab.json`.

## Passo 5: páginas e visuais
Segmentações comuns em todas as páginas, sincronizadas (Exibir → Sincronizar segmentações):
- `DimRun[RunLabel]` (seleção única, padrão P7c);
- `DimScenario[Scenario]`;
- `DimCandidate[Candidate]`.

Em toda página, coloque uma caixa de texto fixa: **"Simulação. Unidades simuladas (SIM), sem dinheiro real."**

### 1. Resumo executivo
- Cartões: `Torneios Hero`, `ROI Agregado`, `ITM %`, `Lucro por Torneio (buy-ins)`, `Vitórias`.
- **Gráfico de barras** de `ROI Agregado` por `DimFieldClass[FieldClassLabel]` × `DimCandidate[Candidate]`.
- Linha constante em `ROI Campo Igual (referência)` (−9,1%) pelo painel Análise → Linha constante.
- **Tabela de status do champion**: `DimCandidate[Candidate]`, `RoleInRun`, `PromotionDecision`, `PromotionReason`.

### 2. Campo explorável × agressivo/adaptativo
- **Matriz**: linhas `DimFieldClass[FieldClassLabel]` → `DimScenario[Scenario]`; colunas `DimCandidate[Candidate]`; valor `ROI ± texto` (a estimativa com o IC 95% do relatório).
- **Gráfico de dispersão "floresta"**: eixo X `ROI (relatório)`, eixo Y `DimScenario[Scenario]`, legenda `Candidate`, barras de erro com `ROI IC Inferior` / `ROI IC Superior` (Análise → Barras de erro).
- Cartão condicional: `Amostra Suficiente`. Use formatação condicional para esmaecer o valor quando ele for "insuficiente".

### 3. Champion × desafiante
- **Tabela** a partir de `FactPairedComparison`, filtrada por `IsDecisionTest = 1`. Colunas:
  - `DimScenario[Scenario]`, `DimCandidate[Candidate]`;
  - `Diferença Pareada`, `Diferença IC Inferior`, `Diferença IC Superior`;
  - `p Holm`, `Relevância Prática`, `Decisão de Promoção`.
- **Floresta**: dispersão com barras de erro de `Diferença Pareada`, com linha constante em 0 e faixa ±0,10 (`Delta Relevância`).
- Texto fixo: "Inconclusivo ≠ equivalência. A decisão segue a regra congelada antes da execução."

### 4. Posição e stack
- **Barras**: `bb por 100 Mãos` por `DimPosition[Position]`, ordenado pela posição.
- **Barras**: `bb por 100 Mãos` por `DimStackBucket[StackBucket]`.
- **Tabela de IC** (de `FactBreakdownCI`): `Dimension`, `Group`, `Hands`, `BBPerHand`, `BBPerHandCiLow`, `BBPerHandCiHigh`, `Flag`.
  - Os ICs existem para o cenário primário de cada execução.

### 5. Decisões
- **Barras 100% empilhadas**: `% Fold`, `% Check/Call`, `% Bet/Raise` por `FactDecision[Street]`.
- **Barras**: `Decisões` por `FactDecision[Component]`, para ver qual parte do agente decidiu (push/fold, abertura, defesa, pós-flop…).
- Cartões: `Margem Equity − Pot Odds`, `Latência Média (ms)`, `Ações Inválidas` (deve ser 0) e `Fallbacks`.

### 6. Variância e sorte
- **Histograma**: `FactEntryResult[NetBuyIns]` (hero) agrupado em compartimentos de 0,5.
- **Tabela** de `FactAllinLuck`: `AllinHands`, `LuckBBMean`, `LuckBBMeanCiLow`, `LuckBBMeanCiHigh`.
- **Linha**: `FactProgressive[Roi]` por `SampleN`, com as bandas de IC. Mostra como a incerteza encolhe com a amostra.

### 7. Steal e re-steal (P7c)
- **Tabela** de `FactSteal`: `StealRate`, `WonImmediately`, `NetPerSteal` com o IC, `VsRestealFold`, `VsRestealCall`, `StealRateFirstHalf`, `StealRateSecondHalf`.
- **Floresta** de `FactStealByDimension`: `NetPerSteal` por `Group`, com segmentação em `Dimension` (posição, stack efetivo, ante, classe do defensor, tamanho da abertura).

### 8. Versões e auditoria
- **Tabela** `DimCandidate`: `Candidate`, `VersionLabel`, `Algorithm`, `Checkpoint`, `BluffRate`, `RoleInRun`, `PromotionDecision`.
- **Tabela** `DimRun`: `RunLabel`, `SeedRoot`, `SetRole`, `PrimaryScenario`, `CodeVersion`.
- Cartões de integridade, que devem mostrar 0:
  - `Checagem Ledger (deve ser 0)`;
  - `Checagem ROI (linhas − relatório)` (com 1 cenário × 1 candidato selecionado);
  - `Problemas de Auditoria`;
  - `Ações Inválidas`.

## Passo 6: conferência final
Com `P7c`, `robust_mix` e `hybrid_v1` selecionados, os valores devem ser:

| Medida | Valor esperado (relatório congelado) |
|---|---|
| `Torneios Hero` | 400 |
| `ROI Agregado` e `ROI (relatório)` | +76,5% |
| `ROI ± texto` | +76,5% [+53,3%; +100,5%] |
| `ITM %` | 36,5% |
| `Checagem ROI (linhas − relatório)` | 0,0000 |

Com `P7c`, `robust_mix` e `hybrid_v2_adaptive`:
- `Diferença Pareada` (decisão) = −0,248 [−0,466; −0,022];
- `p Holm` = 0,2339;
- `Relevância Prática` = "piora (relevância incerta)".

Se algum valor divergir, a montagem tem um problema (relacionamento ou filtro). Os dados em si já foram reconciliados na exportação.

## Atualização
Rode de novo `poker-lab export powerbi` (a pasta é substituída de forma atômica) e clique em **Atualizar** no Power BI.
