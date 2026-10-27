# Protocolo de avaliação (P7)

Código: `evaluation/protocol.py`, `evaluation/report.py`, `scripts/run_p7_evaluation.py`.

## Pergunta
Algum candidato mostra **vantagem de ROI estatisticamente sustentada** contra um campo simulado de adversários em MTT NLHE 6-max? E a vantagem se mantém quando o cenário muda?

## Desenho
- **Unidade experimental**: um torneio independente. Um assento *hero* joga o candidato; os outros 11 assentos são o campo.
- **Números aleatórios comuns (CRN)**: para cenário *s* e índice *k*, todos os candidatos jogam com a mesma seed. Isso fixa assentos, seeds dos agentes do campo e seeds dos baralhos. As diferenças entre candidatos são comparações **pareadas** por *k*.
  - O pareamento reduz variância mas não elimina divergência: quando as decisões do hero mudam, as mãos seguintes divergem.
- **Candidatos**:
  - `random`, `heuristic` (baseline das comparações pareadas);
  - `equity` (Monte Carlo, 120 amostras);
  - `equity_icm_adaptive` (o mesmo com ICM perto do dinheiro e perfil de oponentes);
  - `pushfold_policy` (MCCFR push/fold, com fallback no Equity).
- **Campo (perfis heurísticos documentados em `agents/registry.OPPONENT_PROFILES`)**: `tag`, `lag`, `nit`, `station`, `random`; `mixed` alterna tag/lag/nit/station.
- **Cenários de sensibilidade**: baseline (mixed, n=400); campo só lag, só nit, só station (n=120 cada); campo aleatório (n=60); turbo com stack curto (n=120); reentrada até 3 entradas nos 3 primeiros níveis (n=120); premiação top-heavy 65/35 (n=120). Todos com buy-in 100 + taxa 10 SIM e 12 jogadores (2 mesas).
- **Amostras progressivas**: no baseline, ROI e IC em n = 25, 50, 100, 200, 400, para mostrar o IC encolhendo e o risco de concluir cedo.
- **Intervalos**: bootstrap percentil 95%, com 2.000 reamostragens e seed fixa.
  - ROI agregado: bootstrap de razão sobre torneios.
  - Diferenças pareadas: bootstrap da média das diferenças por *k*.
  - Recortes por mão: **bootstrap por cluster** (reamostra torneios inteiros, porque mãos do mesmo torneio são dependentes).
- **Regra de conclusão** (definida antes de rodar):
  - n < 200 torneios dá `insufficient_sample`, sem afirmar nada;
  - IC inteiro > 0 dá `evidence_positive` *no simulador*;
  - IC inteiro < 0 dá `evidence_negative`;
  - caso contrário, `inconclusive`.
  - Média positiva com IC cruzando zero **não** é vantagem.
  - Nenhum veredito vale para dinheiro real.
- **Recortes** (cenário baseline):
  - bb/mão por fase, posição e faixa de stack inicial;
  - mix de ações e tipo de pote;
  - margem `equity − pot odds` nos calls;
  - "sorte de all-in" (resultado − EV de all-in, calculado offline com as cartas reveladas **depois** da mão).
  - Faixas com menos de 100 mãos ou calls são marcadas `insufficient_sample`.
- **Perfil de adversário**: avaliado pelos cenários de campo homogêneo (lag/nit/station/random), porque o campo misto não permite atribuir cada mão a um único perfil.

## Limitações estatísticas
1. Resultados de MTT têm cauda pesada: o bootstrap percentil pode subcobrir com n pequeno.
2. Os 9 cenários × 5 candidatos são muitas comparações. Sem correção de multiplicidade, ~5% dos ICs "significativos" podem ser falsos positivos. Trate resultados isolados com cautela.
3. Os adversários são heurísticos fixos e não adaptativos. Vantagem contra eles não implica vantagem contra humanos ou bots fortes.
4. Torneios de 12 jogadores com estrutura rápida não representam MTTs grandes (centenas de jogadores, ICM mais forte).
5. A métrica de decisão (`equity − pot odds`) usa equity contra mãos aleatórias, ou top-X% pré-flop: é aproximação, não EV de solver.
