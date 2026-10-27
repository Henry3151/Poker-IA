# Treinamento MCCFR e política push/fold: definição e auditoria (P7)

Números medidos por `scripts/audit_mccfr.py` (saída em `artifacts/p7/mccfr_audit.json`) e por `scripts/run_p7_evaluation.py train` (`artifacts/p7/training_p7.json`).

## 1. Algoritmo
- **External-sampling MCCFR** (`training/mccfr.py`): regret matching, média de estratégia acumulada nos nós do oponente e uma travessia por jogador a cada iteração.
- A iteração *t* usa `Random(derive_seed(seed, "iter", t))`, então N iterações produzem o mesmo resultado que N/2 + N/2 retomadas (há teste para isso).
- **Best response exato** e **exploitability = (BR₀ + BR₁)/2**, calculados por enumeração completa do jogo. Vale 0 num equilíbrio de Nash.
- **Garantia**: em jogos de soma zero para dois jogadores, a estratégia média converge para o equilíbrio. Isso **não** vale para o jogo de 6 jogadores nem para ICM.

## 2. Validação no Kuhn poker (jogo com solução conhecida)
| Iterações | Exploitability | Valor P1 (teórico −0,055556) |
|---|---|---|
| 1.000 | 0,02439 | −0,04210 |
| 10.000 | 0,00713 | −0,05505 |
| 100.000 | 0,00338 | −0,05546 |

Estrutura do equilíbrio: a família de equilíbrios exige *aposta com K = 3α* e *call com Q = α + 1/3*, sendo α a frequência de aposta com J.
- Com α = 0,302, o observado foi K = 0,947 (teórico 0,906) e Q = 0,658 (teórico 0,635).
- Os desvios residuais são compatíveis com a exploitability ainda > 0. A convergência de MCCFR é lenta, da ordem de 1/√T.

## 3. Jogo de referência push/fold (abstração)
| Item | Definição |
|---|---|
| Jogadores | 2 (heads-up), soma zero, chip-EV (sem ICM) |
| Blinds/antes | SB 0,5 bb, BB 1 bb, ante 0 |
| Stack efetivo | 5, 8, 10, 12, 15, 20 bb (um jogo por profundidade) |
| Ações | SB: fold ou all-in (sem limp ou min-raise); BB: fold ou call |
| Cartas | 169 classes; chance = pares de classes ponderados pelo número exato de combos disjuntos (remoção de cartas) |
| Utilidade do call | `eq(A,B)·2S − S`, com `eq` de uma tabela Monte Carlo 169×169 (200 amostras por par; ~0,035 de erro-padrão por célula; simetrizada) |
| Treino P7 | 200.000 iterações por profundidade, seed 20261027, 107,8 s, pico de 23,3 MB, 11.135 it/s |

### Resultado do treino P7 (`pushfold-p7.json`, sha256 `edb1937b…`)
| Stack | Push % (combos) | Call % | Exploitability (bb/mão) |
|---|---|---|---|
| 5 bb | 69,33 | 62,47 | 0,0024 |
| 8 bb | 63,17 | 44,20 | 0,0034 |
| 10 bb | 57,09 | 38,45 | 0,0053 |
| 12 bb | 52,29 | 33,40 | 0,0062 |
| 15 bb | 46,29 | 28,71 | 0,0089 |
| 20 bb | 39,28 | 22,22 | 0,0080 |

### Convergência a 10 bb (tabela 200, seed 11)
2k it: 0,157 · 20k: 0,0297 · 100k: 0,0093 · 200k: 0,0053 bb/mão.

### Sensibilidade ao ruído da tabela de equity (10 bb)
| | Tabela 200 amostras/par | Tabela 600 amostras/par (independente) |
|---|---|---|
| Push % | 59,39 | 58,76 |
| Call % | 37,61 | 37,92 |
| Exploitability no próprio jogo | — | 0,0054 |
| Exploitability da política "200" **dentro do jogo "600"** | 0,0062 | — |

Diferença média por classe: 0,031. Máxima: 0,78, e só 2 classes com diferença > 0,5 (mãos na fronteira, quase indiferentes).

**Atenção**: com a mesma tabela e o mesmo número de iterações, só trocando a seed do solver, o push % a 10 bb variou de **57,09%** (treino P7) para **59,39%** (auditoria). As mãos de fronteira são quase indiferentes, então a porcentagem não é estável. A exploitability, sim (0,0053 em ambos). **O critério de qualidade é a exploitability, não a porcentagem.**

## 4. Comparação com referência publicada (e por que ela não prova equilíbrio)
Fonte: [PokerStrategy — Nash Ranges for the Push-or-Fold Play](https://www.pokerstrategy.com/strategy/sit-and-go/1779/), Tabela 1: heads-up, **sem ante**, push-or-fold, edge 0%, ES = 10. É o **mesmo jogo** da nossa abstração.

| | Push % | Call % |
|---|---|---|
| Publicado | 56,6 | 38,5 |
| Publicado, re-parseado pelo nosso código | 56,56 | 38,46 |
| Nosso (tabela 200, limiar 0,5) | 59,28 | 36,65 |
| Nosso (tabela 600, limiar 0,5) | 56,86 | 37,56 |

Sobreposição dos ranges (Jaccard ponderado por combos):
- **push 0,915 / 0,914** e **call 0,953 / 0,931**.
- Diferenças nas mãos de fronteira:
  - só nosso: 63s, 93s, J7o, Q5o, T3s, T4s, T7o;
  - só publicado: 85s, 97o (e 98o, T5s com a tabela 600);
  - no call, falta J9o e Q8o.

Causas plausíveis, **não verificadas individualmente**:
- ruído Monte Carlo da tabela;
- binarização de estratégias mistas no limiar 0,5;
- convergência incompleta;
- diferenças entre calculadoras (a própria fonte cita ~0,5%).

Por que isso não prova equilíbrio: porcentagens parecidas podem vir de ranges diferentes, e a porcentagem varia com a seed. A evidência relevante é a **exploitability medida no próprio jogo abstrato (~0,005 bb/mão)**. Ela só garante quase-equilíbrio **desse jogo abstrato**, não do NLHE completo.

## 5. Uso no MTT e limitações
- Ativada só em: (a) SB com o pote não aberto até ele e só o BB restante; (b) BB enfrentando all-in do SB, sem mais ninguém na mão. O stack efetivo é arredondado para a profundidade treinada mais próxima (até 23 bb). O resto vai para o EquityAgent.
- **Ignora ICM e antes**, embora o MTT simulado tenha antes a partir do nível 3. O jogo treinado não tem ante, então a política fica um pouco apertada demais nesses spots.
- Num 6-max, o spot "SB vs BB" é raro. O efeito da política no resultado do torneio tende a ser pequeno; veja o `docs/P7_REPORT.md`.
