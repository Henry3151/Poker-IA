# Relatório P7 — Avaliação estatística: a IA tem vantagem em MTT 6-max?

**Resposta curta: não há evidência de vantagem lucrativa.**
- No cenário principal (n = 400 torneios por candidato), todos os candidatos têm ROI negativo ou inconclusivo.
- Nenhum supera o resultado esperado de um campo de jogadores iguais (−9,1%, só a taxa).
- Um adversário heurístico simples e agressivo (LAG) supera todos eles com folga.

Tabelas completas, geradas por script a partir dos dados: `docs/P7_RESULTS_TABLES.md`. Dados brutos: `artifacts/p7/p7_report.json` e `artifacts/p7/p7_lab.db`.

## 1. O que foi executado (medido)
| Item | Valor |
|---|---|
| Torneios simulados | **5.900** (5 candidatos × 8 cenários; 0 falhas) |
| Formato | 12 jogadores, 2 mesas 6-max, buy-in 100 + taxa 10 SIM, top 3 pagos (50/30/20), salvo nos cenários de sensibilidade |
| Tempo | 2 shards × ~1.217 s; consolidação + 114.074 métricas de decisão: ~10 min |
| Integridade | 0 ações inválidas, 0 violações de fichas, 0 `audit_issues`; o ledger reconciliou em todos os torneios (falharia o torneio caso contrário) |
| Reprodutibilidade | seed raiz 20261027. Shards mesclados = execução única (teste); mesma seed por *k* para todos os candidatos (CRN) |
| Testes | **132 passando** (`python -m pytest`), ruff e mypy --strict sem erros |

## 2. Resultados observados — cenário baseline (campo misto tag/lag/nit/station, n = 400)
| Candidato | ROI (IC 95%) | Veredito | ITM | Vitórias | Drawdown máx |
|---|---|---|---|---|---|
| random | −45,7% [−59,6; −31,5] | evidência negativa | 13,0% | 26 | 21.920 |
| heuristic | −39,2% [−50,6; −28,3] | evidência negativa | 23,8% | **0** | 17.350 |
| equity | −39,2% [−53,4; −24,7] | evidência negativa | 16,0% | 24 | 17.410 |
| equity_icm_adaptive | −25,3% [−39,2; −10,0] | evidência negativa | 22,0% | 16 | 13.440 |
| pushfold_policy (MCCFR + equity) | −10,5% [−27,2; +7,2] | **inconclusivo** | 23,0% | 41 | 8.240 |

Para comparação, observados nos assentos do campo, nos mesmos torneios: **LAG +90,4%**, station +6,1%, tag −47,0%, nit −73,1%. Dos torneios do baseline com hero heurístico, o LAG venceu 289 de 400.

**Comparação pareada contra `heuristic`** (mesmas seeds, lucro por torneio em buy-ins de 110):
- `pushfold_policy`: **+0,286 [+0,101; +0,480]**, evidência positiva *relativa ao heurístico*;
- `equity_icm_adaptive`: +0,139 [−0,022; +0,311], inconclusivo;
- `equity`: 0,000, inconclusivo.

**Amostras progressivas** mostram o risco de concluir cedo:
- a `pushfold_policy` tinha ROI **+39,6%** com n = 25 e +22,2% com n = 100;
- com n = 400 caiu para **−10,5%**.
- Uma média positiva com amostra pequena teria levado a uma conclusão falsa.

## 3. Sensibilidade (n = 120 por cenário; n = 60 no campo aleatório) — todos `insufficient_sample` pela regra n < 200
- **Perfil do campo domina o resultado**: com campo só de nits, *todos* os candidatos têm ROI de +167% a +298%. Com campo só de LAGs, todos são negativos (−40% a −85%). O ROI depende mais de quem são os adversários do que do agente.
- **Turbo/stack curto e premiação top-heavy**: a `pushfold_policy` tem o melhor ROI observado (+14,5% e +19,5%), com ICs que cruzam zero. A diferença pareada vs. heurístico é positiva (+0,60 e +0,66 buy-ins), mas n = 120.
- **Reentrada**: a `pushfold_policy` fica pior que o heurístico (−0,12, inconclusivo). O agente aleatório reentra 118 vezes e piora o ROI (−58,9%), e as reentradas e taxas são contadas sem duplicidade.
- **Campo aleatório**: o heurístico tem o maior ROI (+224%, ITM 98%), mas venceu só 2 de 60. Chega sempre ao dinheiro e quase nunca vence.

## 4. Recortes (baseline; IC por cluster de torneio; faixas < 100 mãos sinalizadas)
- **Posição** (heurístico): perde no SB (−0,38 bb/mão) e no BB (−0,32), ganha de BTN/CO/HJ (+0,09 a +0,11). É o padrão esperado de blinds, com os ICs fora de zero.
- **Stack**: a `pushfold_policy` é a única com resultado positivo sustentado em **< 10 bb (+0,165 bb/mão [+0,074; +0,251])**. É exatamente onde a política treinada atua. O equity puro fica em −0,002 nessa faixa.
- **Fase**: na mesa final, equity e equity_icm têm resultado negativo (−0,14 / −0,13 bb/mão). Na fase inicial, todos são inconclusivos.
- **Qualidade de decisão** (somente informação da decisão):
  - o heurístico **desiste em 85% das decisões**;
  - o random paga abaixo das pot odds em 49% dos calls;
  - equity e pushfold pagam abaixo das pot odds em ~0% (margem média equity − pot odds ≈ +0,18 a +0,21).
  - Essa margem usa equity contra mãos aleatórias, ou top-X% pré-flop, e por isso é otimista.
- **Sorte de all-in** (resultado − EV de all-in, offline): ICs contêm zero para todos os candidatos. Por exemplo, pushfold +0,26 bb/mão all-in [−0,23; +0,76]. As diferenças entre candidatos **não** são explicadas por sorte nas mãos all-in.

## 5. Conclusões permitidas pelos dados
1. **Nenhuma evidência de rentabilidade.** Nenhum candidato tem IC de ROI inteiramente positivo no baseline. Os quatro primeiros têm evidência *negativa*.
2. A política MCCFR push/fold, usada em stacks curtos, **melhora o resultado em relação ao heurístico e ao equity puro** neste simulador. A diferença pareada vs. heurístico é positiva com n = 400. O ganho se concentra em < 10 bb, onde a política atua.
   - Ressalvas: comparações múltiplas (4 no baseline) e ROI absoluto ainda inconclusivo.
3. **Os candidatos são mais fracos que um LAG heurístico simples.** Qualquer alegação de "IA forte" seria falsa neste estado.
4. Os heurísticos tight (default, tag, nit) **quase nunca vencem torneios** contra LAGs: falta agressividade em mesa curta e heads-up. É uma fraqueza estratégica identificada, não um erro do motor (0 ações inválidas, 0 inconsistências de fichas).

## 6. Garantias teóricas vs. heurísticas
Detalhado em `docs/STRATEGY_GUARANTEES.md`.
- **Garantia aplicável**: só a política push/fold, como ε-equilíbrio (~0,005 bb/mão de exploitability) do **jogo abstrato heads-up sem ante**.
- **Todo o resto é heurístico**: o uso dessa política no MTT, o EquityAgent, os ajustes de ICM e perfil, e os baselines.
- **Exatos/validados**: avaliador de mãos, motor, ICM (como modelo) e fórmulas de pot odds, EV, SPR e fold equity.
- Auditoria do MCCFR: `docs/TRAINING.md`. A semelhança com a tabela publicada (56,6%/38,5% vs. 57,1%/38,5%) **não** é usada como prova; a porcentagem varia ~2 p.p. com a seed do solver.

## 7. Limitações
- Adversários simulados, fixos e não adaptativos; nenhum humano, nenhum bot forte.
- Torneios de 12 jogadores com estrutura rápida; MTTs reais têm centenas de jogadores e ICM mais forte.
- 40 comparações (8 cenários × 5 candidatos) sem correção de multiplicidade.
- Bootstrap percentil com cauda pesada pode subcobrir.
- Equity de decisão contra ranges simplificados; a política push/fold ignora antes e ICM.
- Banco de avaliação grande (~3,2 GB): mantido fora do Git.

## 8. Recomendação para a próxima fase
Antes de P8, recomendo uma **P7b estratégica** (decisão sua):
1. Incluir o LAG e outros perfis como candidatos e como campo de referência.
2. Corrigir a agressividade em mesa curta e heads-up (por exemplo, push/fold treinado com ante e ICM, e política HU treinada).
3. Repetir o protocolo com n ≥ 400 por cenário relevante, usando correção de multiplicidade (Holm) definida antes.

A P8 (Power BI) pode ser feita em paralelo, porque os dados já estão no modelo relacional. **A camada de execução externa continua desativada** e não deve ser considerada enquanto não houver vantagem demonstrada em simulação e autorização documentada.
