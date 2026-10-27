# Especificação de Dashboard Microsoft Power BI

## Objetivo
Permitir analisar vitórias, derrotas, qualidade de decisões, evolução do agente, erros do motor e desempenho por versão em torneios MTT simulados.

## Fonte de dados
Fonte inicial recomendada: exportações CSV ou Parquet geradas pelo sistema. Power BI Desktop pode conectar-se a arquivos locais. Para um fluxo local simples, exportar snapshots após torneios/experimentos; atualizar automaticamente depende da configuração local e da capacidade do Power BI instalada.

Não presumir que um arquivo `.pbix` pode ser gerado ou validado sem Power BI Desktop. A implementação deve entregar os dados, o modelo de dados, as medidas DAX e instruções de montagem; a validação visual final deve ser feita no Power BI Desktop.

## Modelo estrela sugerido
Fatos:
- `FactTournaments`: uma linha por torneio e versão de agente.
- `FactHands`: uma linha por mão e participante/agente relevante.
- `FactDecisions`: uma linha por decisão.
- `FactTrainingRuns`: uma linha por execução/intervalo de treinamento.
- `FactAgentResults`: uma linha por agente e torneio.
- `FactNotes`: notas categorizadas, se necessário.

Dimensões:
- `DimDate`
- `DimAgentVersion`
- `DimExperiment`
- `DimTournamentConfig`
- `DimPosition`
- `DimStreet`
- `DimAction`
- `DimReasonCategory`

Use chaves inteiras surrogate quando materializar o modelo. Defina relacionamentos um-para-muitos e evite relações bidirecionais ambíguas.

## Páginas do relatório

### 1. Executive Overview
Cards: torneios executados, taxa de vitória, colocação média, retorno médio simulado, bb/100 quando aplicável, taxa de ação inválida, versão champion.
Visuais: evolução temporal, distribuição de colocação, comparação champion/challenger.
Filtros: período, experimento, versão, estrutura de blinds, número de participantes.

### 2. Vitórias e derrotas
- vitórias, eliminações e colocações;
- distribuição de resultados por versão;
- taxa de mesa final e de vitória;
- retorno simulado por configuração de prêmio;
- intervalos de confiança e tamanho da amostra.

### 3. Qualidade das decisões
- decisões por ação e street;
- estimativa de EV por ação, se disponível;
- divergência entre ação escolhida e benchmark de referência;
- decisões marcadas para revisão;
- taxa de ações inválidas/timeout.

### 4. Motivos de resultado
Visual por categorias: decision_quality, variance, opponent_adaptation, tournament_dynamics, execution_issue, rule_or_engine_bug e insufficient_evidence.
Mostrar contagem, proporção, confiança/qualidade da evidência e links para detalhes. Não converter correlação em causalidade.
Separar motivo observado, hipótese automatizada e revisão humana.

### 5. Treinamento
- iterações/episódios;
- tempo de execução;
- throughput;
- uso de memória/CPU quando medido;
- performance contra baselines;
- versões de checkpoints e resultado da avaliação.

### 6. Auditoria e erros
- erros do motor;
- falhas de execução;
- ações inválidas;
- inconsistências de fichas;
- dados ausentes;
- divergências de reconciliação.

### 7. Hand Review
Tabela filtrável por torneio, mão, street, posição, stack efetivo e decisão.
Mostrar cartas próprias do agente e board de forma controlada, ação escolhida, ações legais, estimativas registradas, resultado e notas de revisão. Cartas ocultas só aparecem em relatório offline autorizado de simulação, nunca na observação usada pelo agente.

### 8. Notas e hipóteses
O Power BI pode exibir notas exportadas, mas a edição das notas deve ocorrer na página de anotações do sistema ou no armazenamento apropriado. Power BI não é o banco transacional de anotações.

## Medidas DAX ilustrativas
Os nomes exatos dependem do modelo final. A implementação deve testar e adaptar:

```DAX
Torneios = DISTINCTCOUNT(FactTournaments[TournamentId])

Vitórias =
CALCULATE(
    COUNTROWS(FactAgentResults),
    FactAgentResults[FinalPlace] = 1
)

Taxa de Vitória =
DIVIDE([Vitórias], [Torneios])

Colocação Média =
AVERAGE(FactAgentResults[FinalPlace])

Ações Inválidas =
CALCULATE(
    COUNTROWS(FactDecisions),
    FactDecisions[IsActionValid] = FALSE()
)

Taxa de Ação Inválida =
DIVIDE([Ações Inválidas], COUNTROWS(FactDecisions))
```

A medida de vitória deve contar um resultado por torneio e agente; não conte várias linhas da mesma participação. Verifique a granularidade antes de usar `COUNTROWS`.

## Reconciliação
Cada KPI deve ser comparado com uma consulta SQL ou agregado de referência. Registrar definição, granularidade, filtros e tratamento de dados ausentes. Não publicar ROI simulado sem documentar buy-in e estrutura de premiação simulada.
