# Especificação P8: modelo Power BI (preparada em paralelo; implementação só após o ciclo de robustez)

Baseada nas tabelas que **existem de fato** no banco (migrações 0001 e 0002). Nenhum `.pbix` é gerado nem validado aqui: o Power BI Desktop não está disponível no ambiente de desenvolvimento.

## 1. Alimentação
- Exportação `poker-lab export powerbi` (P8) gera Parquet (com CSV como fallback) em `artifacts/powerbi/<evaluation_run_id>/`. A pasta tem um tipo de arquivo por tabela abaixo e um `manifest.json` com sha256, contagens e versão do schema.
- **Intervalos de confiança não são calculados em DAX** (bootstrap é inviável no modelo). São exportados prontos de `evaluation/report.py`, `evaluation/champion.py` e `stats.py`, como tabelas de fatos de estatística. O DAX só filtra e exibe.
- Atualização: reexportar e "Atualizar" no Power BI (fonte "Pasta"). Cada exportação é imutável e identificada pelo run.

## 2. Modelo estrela
**Dimensões**:

| Tabela | Chave | Origem | Campos principais |
|---|---|---|---|
| `DimAgentVersion` | AgentVersionKey | `agent_versions` | lineage (name), version_label, algorithm, status (champion/candidate/retired/baseline), checkpoint_sha256, premissas (de `docs/MODEL_VERSIONS.md` / checkpoint config) |
| `DimExperiment` | ExperimentKey | `experiments` + `evaluation_runs` | run, seed raiz, **papel do conjunto (dev / final / P7)**, protocolo, code_version |
| `DimScenario` | ScenarioKey | `tournaments.scenario_label` | scenario, field_profile/mix, **FieldClass**, estrutura (stack, níveis, reentrada, premiação) |
| `DimOpponentProfile` | ProfileKey | rótulos de campo | tag, lag, nit, station, random, adaptive_tag, adaptive_lag, bluffer40/60, maniac, hybrid-v1, p7…; **FieldClass** |
| `DimPosition` | PositionKey | fixo | BTN, SB, BB, UTG, HJ, CO… e ordem |
| `DimStackBucket` | BucketKey | fixo | <10bb, 10-20bb, 20-40bb, 40bb+ |
| `DimPhase` | PhaseKey | `hands.phase` | early, middle, bubble, itm, final_table |
| `DimAction` / `DimPotType` | — | `decisions` / `decision_metrics` | fold/check/call/bet/raise; unopened/limped/single_raised/3bet+/postflop |
| `DimDate` | DateKey | timestamps | — |

**FieldClass** é o agrupamento pedido para separar os resultados:
- `exploitable_static`: tag, nit, station, random e o campo misto original;
- `aggressive_static`: lag, maniac, bluffer40/60;
- `adaptive`: adaptive_tag, adaptive_lag;
- `self_play`: campos com versões do próprio agente.

**Fatos**:

| Tabela | Grão | Origem |
|---|---|---|
| `FactEntryResult` | 1 linha por (torneio, participante) | `v_entry_financials` + `tournament_entries` (place, payout, buy_ins_total, fees_total, net_profit, roi, itm, entries_count, role hero/field) |
| `FactLedger` | 1 linha por movimento | `financial_ledger` (reconciliação) |
| `FactHandHero` | 1 linha por (mão, hero) | `hand_players` + `hands` (net_bb, position, stack_bucket, phase, all-in EV/sorte) |
| `FactDecision` | 1 linha por decisão do hero | `decisions` + `decision_metrics` (action, pot_type, equity, pot_odds, ev_call, component do agente) |
| `FactPairedComparison` | 1 linha por (run, cenário, challenger vs champion) | report/champion: estimate, ci_low, ci_high, n, p, p_holm, verdict |
| `FactScenarioSummary` | 1 linha por (run, cenário, candidato) | report: ROI + IC, ITM + IC, wins, drawdown, quantis |
| `FactBreakdownCI` | 1 linha por (run, cenário, candidato, dimensão, faixa) | report: bb/mão + IC por cluster, hands, flag |
| `FactTrainingRun` | 1 linha por run de treino | `training_runs` (iterações, exploitability, tempo, memória) |
| `FactEvaluationDecision` | 1 linha por decisão de promoção | `evaluations` |
| `FactAudit` | 1 linha por problema | `audit_issues` |

Relacionamentos um-para-muitos, das dimensões para os fatos, com filtro em direção única.

## 3. Medidas DAX (granularidade verificada)
```DAX
Torneios Hero = CALCULATE(DISTINCTCOUNT(FactEntryResult[TournamentId]), FactEntryResult[Role] = "hero")
Custo Hero = CALCULATE(SUM(FactEntryResult[BuyInsTotal]) + SUM(FactEntryResult[FeesTotal]), FactEntryResult[Role] = "hero")
Lucro Hero = CALCULATE(SUM(FactEntryResult[NetProfit]), FactEntryResult[Role] = "hero")
ROI Agregado = DIVIDE([Lucro Hero], [Custo Hero])            -- igual a evaluation/finance.summarize
ITM % = DIVIDE(CALCULATE(COUNTROWS(FactEntryResult), FactEntryResult[Role] = "hero", FactEntryResult[ITM] = 1), [Torneios Hero])
bb por mão = DIVIDE(SUM(FactHandHero[NetBB]), COUNTROWS(FactHandHero))
IC Inferior ROI = MIN(FactScenarioSummary[RoiCiLow])      -- vem pronto da exportação; só tem sentido filtrado em 1 cenário x 1 candidato
IC Superior ROI = MAX(FactScenarioSummary[RoiCiHigh])
Amostra Suficiente = IF(MIN(FactScenarioSummary[NTournaments]) >= 200, "sim", "insuficiente")
```
Regra visual: quando "Amostra Suficiente" = insuficiente, o card mostra o aviso e esmaece o valor.

## 4. Páginas
1. **Resumo executivo**: champion atual e premissas; ROI com IC por **FieldClass**; aviso fixo de "simulação, sem dinheiro real".
2. **Campo explorável × LAG/adaptativo**: ROI e IC por FieldClass e por perfil; gráfico de barras com barras de erro (IC).
3. **Champion × challenger**: `FactPairedComparison` com estimativa, IC, p e p_Holm; decisões de `evaluations`.
4. **Posição e stack**: bb/mão com IC por posição e por faixa de stack; flags de amostra.
5. **Decisões**: mix de ações, tipo de pote, margem equity − pot odds, componente do agente que decidiu.
6. **Variância e sorte**: distribuição de lucro, drawdown, sorte de all-in.
7. **Versões e experimentos**: versão, sha256, seeds, conjunto (dev/final), treino.
8. **Auditoria**: reconciliação do ledger, ações inválidas, integridade.

## 5. Reconciliação obrigatória
Cada KPI (ROI, ITM, lucro, nº de torneios, bb/mão) é recalculado em SQL e comparado com os arquivos exportados. O resultado vai para `reconciliation.json`, e uma divergência bloqueia a exportação.
