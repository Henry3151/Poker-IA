# Relatório P7b — Melhoria estratégica

Fontes dos números (todos medidos):
- `artifacts/p7b/diagnosis.json` (auditoria da P7)
- `dev_analysis.json` e `calibration.json` (conjunto de desenvolvimento)
- `p7b_final_report.json` e `hybrid_vs_lag.json` (avaliação final)
- tabelas completas: `docs/P7B_RESULTS_TABLES.md`
- cópias versionadas: `docs/p7b_artifacts/`

## 1. Separação dos dados
| Conjunto | Seed raiz | Uso |
|---|---|---|
| P7 | 20261027 | Auditoria (somente leitura) |
| Desenvolvimento | 777001 | Diagnóstico com gravação completa (180 torneios), calibração do `bluff_rate`, checagem dos challengers (300 torneios) |
| Avaliação final | 20261028 | **Nunca usada para ajuste**: 9.100 torneios, critérios fixados antes de rodar |

## 2. Causas: confirmadas, hipóteses e limitações
**Infraestrutura (Fase A), sem defeito:**
- contabilidade fecha em 5.900 de 5.900 torneios;
- 0 inconsistências de fichas, 0 ações inválidas;
- seeds idênticas entre candidatos; assento do hero idêntico por seed (1.180 de 1.180).

| Id | Causa | Evidência | Status |
|---|---|---|---|
| C1 | Política push/fold treinada **sem ante**, usada com ante | 97% das decisões da política (5.425 de 5.575) ocorreram com ante | **Confirmada**. A correção isolada (`v2-ante`) teve efeito pequeno e inconclusivo no baseline (+0,03 buy-in) e positivo no turbo (+0,19 [+0,03; +0,37]; Holm p = 0,08) |
| C2 | Pós-flop "calling station": equity contra mãos aleatórias superestima | Na desenvolvimento, a equity estimada nos calls diante de aposta superou a real (calculada offline contra as cartas do apostador) em +0,16 no flop, +0,22 no turn e +0,33 no river, com ICs fora de zero. Com o filtro de range de aposta (`bluff_rate` = 0), o viés caiu para +0,009 [−0,013; +0,033] | **Confirmada e corrigida** |
| C3 | Abre pouco e não rouba blinds | Open-raise foi a linha mais lucrativa de todos os agentes. O campo desiste dos blinds contra steal em 77–98% (tag 97%, nit 98%). O Equity abria só 10–12% no BTN/CO | **Confirmada**. É o principal mecanismo de ganho do híbrido |
| C4 | SB completa passivamente | Equity: 1.308 limps a −0,35 bb/mão | Corrigida no híbrido (raise ou fold) |
| H5 | LAG vence por explorar a defesa fraca dos blinds de tag/nit | O LAG ganha mais em CO (+0,67 bb/mão) e BTN (+0,43). Desiste em 82,5% diante de c-bet | Consistente com os dados; mecanismo comum ao híbrido |
| — | Heurístico default nunca vence | VPIP 10%, desiste do BB em 95% contra open | Fraqueza do baseline, que foi mantido **imutável** |

**Limitação**: os quatro perfis do campo são heurísticos fixos. O leak que o híbrido explora (desistir demais dos blinds) é **específico desta configuração**.

## 3. Mudanças (pequenas, testáveis, sem reescrever o motor, o banco ou o torneio)
| Arquivo | Mudança | Justificativa |
|---|---|---|
| `training/games.py`, `pushfold_trainer.py`, `checkpoints.py` | Push/fold com ante e dinheiro morto; contextos versionados no checkpoint | C1 |
| `agents/policy_agent.py` | Escolha do contexto treinado (ante → dinheiro morto → stack); stack efetivo inclui antes | C1 |
| `strategy/preflop_model.py` | Equity classe-vs-range, ranges de open por posição, EV de shove | C3/C4, defesa de blinds |
| `strategy/postflop_ranges.py` | Filtro de range de aposta | C2 |
| `agents/hybrid.py` | Challenger `hybrid-v1` | C1–C4, ICM nos all-ins |
| `evaluation/champion.py` | p-valor bootstrap, Holm, decisão e promoção transacional | Champion/challenger |
| `evaluation/protocol.py` | `record_level` configurável (gravação completa no desenvolvimento) | Diagnóstico do campo |
| `application/training_service.py` | Contextos e premissas do modelo gravados no checkpoint | Reprodutibilidade |
| `scripts/p7b_*.py` | Diagnóstico, desenvolvimento, calibração, treino v2, avaliação final | — |

Os agentes antigos (Random, Heuristic, Equity, `pushfold@p7`) **não foram alterados** em comportamento. O checkpoint P7 está somente leitura (sha256 `edb1937b…`). Versões e premissas: `docs/MODEL_VERSIONS.md`.

## 4. Testes
- **149 testes passando** (132 anteriores + 17 novos); ruff e mypy --strict sem erros.
- Os novos cobrem:
  - utilidades do jogo com ante;
  - ampliação do push com dinheiro morto;
  - seleção de contexto;
  - equity contra range completo = equity contra mão aleatória;
  - propriedades do EV de shove;
  - filtro de aposta;
  - roteamento do híbrido;
  - "nunca limpa first-in";
  - sessão sem ações inválidas;
  - **invariância do híbrido a cartas ocultas e futuras**;
  - Holm (valor de referência);
  - calibração do p-valor sob a hipótese nula (5% nominal);
  - regras de decisão e promoção transacional.

## 5. Champion × challenger: avaliação final independente
**Critérios fixados antes de rodar:**
- cenário principal baseline, n ≥ 400;
- IC 95% da diferença pareada > 0;
- Holm p < 0,05 sobre 2 challengers × 3 cenários;
- sem regressão (IC < 0) no campo LAG ou no turbo;
- 0 ações inválidas.

| Challenger − `pushfold@p7` (buy-ins/torneio) | Baseline n = 400 | Campo LAG n = 200 | Turbo n = 200 | Decisão |
|---|---|---|---|---|
| `v2-ante` | +0,033 [−0,090; +0,153]; p_Holm = 1,00 | +0,016 [−0,093; +0,115] | +0,191 [+0,027; +0,365]; p_Holm = 0,081 | inconclusivo |
| `hybrid-v1` | **+0,998 [+0,742; +1,249]; p_Holm = 0,0015** | +0,322 [+0,049; +0,567]; p_Holm = 0,064 | +0,485 [+0,065; +0,873]; p_Holm = 0,064 | **promovido** |

Cenários de sensibilidade (n = 100; `insufficient_sample` pela regra), diferença `hybrid-v1` − `p7`:

| Cenário | Diferença [IC 95%] |
|---|---|
| tag | +1,20 [+0,60; +1,80] |
| nit | +1,47 [+0,98; +1,99] |
| station | +0,32 [−0,19; +0,80] |
| reentrada | +1,14 [+0,45; +1,76] |
| top-heavy | +1,28 [+0,67; +1,90] |

O sinal é positivo em todos os cenários.

**ROI absoluto, baseline (n = 400):**
- `hybrid-v1`: +89,5% [+66,6; +114,4], ITM 42,5%, 108 vitórias;
- `p7`: −10,3% [−28,8; +7,7];
- LAG: +69,1% [+47,8; +90,1];
- Equity: −43,3%; Heurístico: −31,3%; Random: −41,4%.

**Campo só LAG:**
- `hybrid-v1`: −22,0% [−44,4; +1,5];
- LAG: +5,8% [−17,6; +31,5].

**Híbrido × LAG** (pareado):

| Cenário | Diferença [IC 95%] | Leitura |
|---|---|---|
| baseline | +0,21 [−0,08; +0,51] | inconclusivo |
| campo LAG | −0,28 [−0,60; +0,04] | inconclusivo |
| station | +0,68 [+0,16; +1,24] | n = 100 |
| tag | −0,39 [−0,91; +0,12] | n = 100 |

**Não há evidência de que o híbrido seja melhor que um LAG heurístico simples.**

**Recortes (baseline, bb/mão, IC por cluster de torneio):**
- o ganho do híbrido vem de BTN (+0,60 [+0,48; +0,72]), CO (+0,57), HJ (+0,33) e SB (+0,28);
- o BB fica neutro (+0,07 [−0,10; +0,22]); o `p7` perdia no BB (−0,36 [−0,64; −0,09]);
- positivo em todas as faixas de stack e na mesa final (+0,24 [+0,15; +0,33]).

**Sorte de all-in:** híbrido +0,22 bb/mão all-in [−0,14; +0,59]. O IC contém zero, e a diferença não é explicada por sorte.

## 6. Conclusões permitidas
1. Existe uma **melhoria estratégica que sobreviveu a teste independente**: o `hybrid-v1` supera o champion anterior em todos os cenários testados. A melhoria é estatisticamente sustentada no cenário principal, mesmo com correção para comparações múltiplas. Foi promovido a champion pelas regras definidas antes.
2. O mecanismo principal é **roubar blinds e jogar mais agressivo em posição tardia**, explorando um campo que desiste demais. É um leak real *desses* adversários. **Não é evidência de força contra humanos ou bots competentes**, e o híbrido empata, sem diferença significativa, com um LAG heurístico.
3. A correção de ante isolada (`v2-ante`) não teve efeito detectável no baseline. No turbo, onde stacks curtos e antes são frequentes, o efeito é positivo mas não sobrevive à correção de Holm.
4. **Nenhuma alegação de rentabilidade real.** O ROI positivo é de um simulador com adversários fixos e exploráveis. Contra um campo só de LAGs, o resultado é negativo ou inconclusivo.

## 7. Problemas não resolvidos
- O campo não tem adversários adaptativos nem fortes. Uma política que vence perfis fixos pode ser explorável.
- O `bluff_rate` = 0 foi calibrado contra perfis que blefam pouco quando apostam. Contra blefadores frequentes, o híbrido desistirá demais.
- O pós-flop continua heurístico (sem árvore de decisão, sem sizing ótimo, sem textura além do filtro).
- O ICM é usado só em calls de all-in; a política push/fold ignora ICM.
- A métrica "calls abaixo das pot odds" usa equity contra mãos aleatórias no pré-flop. Para o híbrido, que decide contra o range do agressor, ela superestima erros (14,7%).
- Torneios de 12 jogadores não representam MTTs grandes.

## 8. Recomendação
**Continuar a P7b por mais um ciclo antes da P8**, focado em robustez e não em ROI:
1. adicionar ao campo de avaliação adversários **adaptativos** (que ajustam a defesa de blinds contra quem rouba) e o próprio `hybrid-v1` (self-play);
2. avaliar o híbrido contra campos com blefe frequente (sensibilidade do `bluff_rate`);
3. só então tratar `hybrid-v1` como baseline estável para a P8.

A especificação do Power BI pode ser preparada em paralelo, sem bloquear. A camada de execução externa continua **desativada**.
