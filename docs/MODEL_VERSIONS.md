# Versões de modelo (registro imutável)

Os checkpoints ficam em `artifacts/checkpoints/` (fora do Git, **somente leitura**), cada um com um `.meta.json` contendo o sha256. Um modelo nunca é sobrescrito: versão nova = arquivo novo.

| Versão | Arquivo | sha256 | Premissas de treino | Status |
|---|---|---|---|---|
| `pushfold@p7` | `pushfold-p7.json` | `edb1937b765c6bdc530eb13b36258fb688886982a983dfb54f93b5b5e4b43756` | Push/fold heads-up (SB fold/all-in, BB fold/call), 169 classes, chip EV, **sem ante**, stacks 5/8/10/12/15/20 bb; tabela de equity MC 200 amostras/par, seed 20261026; MCCFR external sampling, 200.000 it/stack, seed 20261027 | retired (baseline imutável; substituída pela decisão da P7b) |
| `pushfold@v2-ante` | `pushfold-v2-ante.json` | `d3e7d9caf73b7e45e11c1f7106692c56963d6c83705247c298649d2f2340da4c` | Mesmo jogo, agora com **ante** *a* pago por SB e BB e **dinheiro morto** *d* = antes de quem já desistiu. Contextos (a, d): (0, 0), (0,125, 0), (0,125, 0,125), (0,125, 0,25), (0,125, 0,375), (0,125, 0,5) × stacks 5/8/10/12/15/20 bb; mesma tabela de equity; 150.000 it/contexto, seed 20261101; exploitability média 0,0073 bb/mão | candidate (inconclusivo na P7b) |
| `pushfold@hybrid-v1` | usa `pushfold-v2-ante.json` + tabela `hu_class_equity_s200_seed20261026.json` | (o checkpoint acima) | Agente híbrido: push/fold v2 nos spots SB-vs-BB; open/shove por posição; defesa por equity contra o range do agressor; pós-flop com filtro de range de aposta (`bluff_rate` = 0,0, calibrado **só** no conjunto de desenvolvimento); c-bet 70%; ICM nos all-ins perto do dinheiro | **champion** (promovido na P7b, avaliação final seed 20261028) |
| `pushfold@hybrid-v2-adaptive-b0.2` | mesmo checkpoint e tabela do `hybrid-v1` | (o checkpoint acima) | `hybrid-v1` + ajuste de abertura e re-steal pelo comportamento observado dos defensores (`adaptive_steal`); `bluff_rate` = 0,2 | **não promovido** (P7c, seed final 20261029: piora no cenário primário, relevância incerta; ver `docs/P7C_REPORT.md`) |
| `pushfold@hybrid-v1-b0.2` | mesmo checkpoint e tabela do `hybrid-v1` | (o checkpoint acima) | `hybrid-v1` com `bluff_rate` = 0,2 (controle) | **não promovido** (P7c) |

Parâmetros heurísticos do `hybrid-v1`, congelados antes da avaliação final:
- `OPEN_FRACTION` por jogadores atrás: 1: 60%, 2: 48%, 3: 32%, 4: 24%, 5: 18%;
- `shove_max_bb` = 12;
- 3-bet com top 3,5% ou equity ≥ 0,56 contra o range do agressor com ≤ 25 bb;
- realização de equity 0,9 em posição / 0,75 fora;
- margem de call 0,01 pré-flop / 0,02 pós-flop;
- value bet com equity ≥ 0,62 heads-up;
- c-bet 40% do pote.

## Separação de dados (seeds raiz)
| Uso | Seed raiz |
|---|---|
| P7 (avaliação original, preservada) | 20261027 |
| P7b desenvolvimento (diagnóstico, calibração, checagem) | 777001 |
| P7b avaliação final (nunca usada para ajustar) | 20261028 |
| P7c desenvolvimento (escolha de β) | 777002 |
| P7c avaliação final (nunca usada para ajustar) | 20261029 |
