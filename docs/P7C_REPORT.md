# P7c: ciclo de robustez (relatório final)

**Decisão: o `hybrid-v1` continua champion. A hipótese de que um desafiante robusto o supera não foi confirmada.**

Nenhum dos dois desafiantes cumpriu a regra pré-registrada. Os dois tiveram estimativa pontual negativa nos 6 cenários. No cenário primário, o IC 95% ficou inteiramente abaixo de zero, o que por si só aciona o critério "nenhuma regressão" e impede a promoção. Depois da correção de Holm para os 12 testes, porém, essa piora **não** é estatisticamente significativa (p Holm = 0,234). Por isso este relatório fala em "piora com relevância incerta", e não em "piora comprovada".

Unidades simuladas (SIM). Nada aqui é evidência de lucro com dinheiro real.

## 1. Plano congelado antes da execução
| Item | Valor |
|---|---|
| Commit do plano | `52db436` no histórico original; `2c28d55` após a limpeza de metadados do histórico. O código é idêntico: `scripts/p7c_final.py` tem sha256 `9f058432…` nos dois |
| Seed raiz final | 20261029 (nunca usada para ajuste). Desenvolvimento: 777002 |
| Champion | `hybrid-v1` (P7b) |
| Desafiantes (escolhidos no conjunto de desenvolvimento) | `hybrid_v2_adaptive`: abre e re-rouba conforme o comportamento observado dos defensores, com β = 0,2. `hybrid_v1_bluffcatch`: v1 com β = 0,2, que assume 20% de blefes no range de aposta do adversário (controle) |
| Referências | `lag` (perfil heurístico agressivo) e `pushfold_p7` |
| Cenários (n por candidato) | robust_mix 400 (primário) · adaptive_only 200 · bluff_heavy 200 · baseline_mixed 200 · selfplay_hybrid 100 · versions_mix 100 |
| Unidade de randomização | Torneio. Common random numbers: mesma seed por (cenário, k) para todos os candidatos |
| Regra de promoção | IC primário > 0 **e** Holm p < 0,05 (12 testes); nenhum cenário com IC inteiramente < 0; estimativa ≥ 0 em pelo menos 4 dos 6 cenários; zero ações inválidas |
| Relevância prática | δ = 0,10 buy-in por torneio |

## 2. Execução e integridade dos dados
- **6.000 torneios** (5 candidatos × 1.200), em 2 shards.
- **Incidente operacional:** às ~11:30 o ambiente reiniciou e interrompeu os dois shards em cerca de 2.850/3.000 torneios. O tratamento seguiu esta ordem:
  1. os bancos foram preservados com checksums **antes** de qualquer ação;
  2. só os 2 torneios incompletos foram removidos;
  3. os shards foram retomados com o comando congelado e as mesmas seeds.

  Também houve um desvio na preservação: o checkpoint WAL de uma das cópias preservadas alterou os bytes do arquivo, mas não seu conteúdo lógico. Os detalhes estão em [`p7c_artifacts/INCIDENT_20261027.md`](p7c_artifacts/INCIDENT_20261027.md).
- **Verificação de integridade** (`scripts/p7c_integrity.py`, somente leitura; [`p7c_integrity.json`](p7c_artifacts/p7c_integrity.json)), todas aprovadas:

| Verificação | Resultado |
|---|---|
| Todos os torneios `completed` | 6.000/6.000 |
| Completude por (cenário, candidato) contra a escala congelada | 30/30 células corretas |
| Pareamento CRN (mesmo conjunto de seeds por cenário) | ok |
| Exatamente um herói por torneio | ok |
| Conciliação do ledger (buy-ins, taxas, prêmios) | 0 falhas |
| Conservação do dinheiro (prêmios = prize pool; soma dos lucros = −taxas) | 0 falhas |
| Ações inválidas registradas (todos os participantes) | 0 |
| Torneios duplicados | 0 |
| `PRAGMA quick_check` | ok |

## 3. Resultado principal: desafiante − champion (testes da regra congelada)
Diferença pareada de lucro por torneio, em buy-ins (100 + 10). IC 95% por bootstrap percentil. p-valor por bootstrap sob a hipótese nula deslocada, com correção de Holm sobre os 12 testes.

**hybrid_v2_adaptive** − hybrid_v1 · decisão: `keep_champion` (regression (CI < 0) in ['robust_mix']) · estimativas ≥ 0: 0/6 · ações inválidas: 0

| cenário | n | diferença (buy-ins/torneio) | IC 95% | p | p Holm | relevância (δ = 0,10) |
|---|---|---|---|---|---|---|
| robust_mix | 400 | -0.248 | [-0.466; -0.022] | 0.0205 | 0.2339 | piora (relevância incerta) |
| adaptive_only | 200 | -0.060 | [-0.316; +0.213] | 0.6646 | 1.0000 | inconclusivo |
| bluff_heavy | 200 | -0.240 | [-0.540; +0.060] | 0.1200 | 1.0000 | inconclusivo |
| baseline_mixed | 200 | -0.038 | [-0.338; +0.284] | 0.8108 | 1.0000 | inconclusivo |
| selfplay_hybrid | 100 | -0.207 | [-0.502; +0.076] | 0.1535 | 1.0000 | inconclusivo |
| versions_mix | 100 | -0.262 | [-0.720; +0.196] | 0.2707 | 1.0000 | inconclusivo |

**hybrid_v1_bluffcatch** − hybrid_v1 · decisão: `keep_champion` (regression (CI < 0) in ['robust_mix']) · estimativas ≥ 0: 0/6 · ações inválidas: 0

| cenário | n | diferença (buy-ins/torneio) | IC 95% | p | p Holm | relevância (δ = 0,10) |
|---|---|---|---|---|---|---|
| robust_mix | 400 | -0.226 | [-0.428; -0.035] | 0.0195 | 0.2339 | piora (relevância incerta) |
| adaptive_only | 200 | -0.060 | [-0.289; +0.180] | 0.6216 | 1.0000 | inconclusivo |
| bluff_heavy | 200 | -0.104 | [-0.393; +0.185] | 0.5006 | 1.0000 | inconclusivo |
| baseline_mixed | 200 | -0.115 | [-0.365; +0.147] | 0.3707 | 1.0000 | inconclusivo |
| selfplay_hybrid | 100 | -0.218 | [-0.480; +0.033] | 0.0995 | 0.9948 | inconclusivo |
| versions_mix | 100 | -0.131 | [-0.622; +0.327] | 0.5868 | 1.0000 | inconclusivo |

![P7c: desafiantes vs champion](assets/p7c_challengers_light.png)

**Leitura**
- **Nenhum cenário favorece os desafiantes:** nenhuma estimativa é positiva e nenhum IC fica acima de +δ.
- **No cenário primário, a piora fica entre 0,22 e 0,25 buy-in por torneio.** O IC exclui zero sem correção, mas não sobrevive à correção de Holm. Como o IC cruza −δ, a relevância prática da piora é incerta.
- **Nos outros cenários, o resultado é inconclusivo, e isso não significa equivalência.** Nenhum IC ficou inteiramente dentro de ±δ.
- **O desenvolvimento já apontava nessa direção:** na seed 777002 nenhuma variante tinha melhorado. O β = 0,2 foi escolhido pela melhor média de desenvolvimento, e não por uma melhora estabelecida.

## 4. ROI por cenário (IC 95%)
Com habilidade igual, o ROI esperado é −9,1%, só por causa da taxa. Em cenários com n = 100, o veredito automático é "amostra insuficiente".

| cenário | hybrid_v1 | hybrid_v2_adaptive | hybrid_v1_bluffcatch | lag | pushfold_p7 |
|---|---|---|---|---|---|
| robust_mix (n=400) | +76.5% [+53.3; +100.5] | +51.6% [+30.6; +74.3] | +53.8% [+32.0; +77.3] | +67.2% [+45.6; +89.0] | -17.1% [-34.5; +1.7] |
| adaptive_only (n=200) | +33.6% [+5.8; +62.0] | +27.6% [-0.2; +58.2] | +27.6% [-0.2; +56.5] | +41.3% [+12.4; +70.2] | -30.2% [-53.1; -6.2] |
| bluff_heavy (n=200) | -1.8% [-28.0; +27.6] | -25.8% [-48.7; +0.9] | -12.2% [-36.7; +16.2] | +9.1% [-17.6; +38.5] | -43.3% [-64.0; -21.5] |
| baseline_mixed (n=200) | +48.9% [+20.5; +82.2] | +45.1% [+14.0; +78.4] | +37.5% [+8.5; +68.0] | +81.1% [+52.7; +110.5] | -2.4% [-28.0; +26.0] |
| selfplay_hybrid (n=100) | -10.5% [-37.8; +18.9] | -31.3% [-57.5; -2.9] | -32.4% [-57.5; -2.9] | -8.4% [-38.9; +26.5] | -50.9% [-73.8; -25.8] |
| versions_mix (n=100) | +41.8% [+4.7; +83.3] | +15.6% [-19.3; +54.9] | +28.7% [-9.5; +66.9] | +35.3% [+0.4; +73.5] | -32.4% [-58.5; -1.8] |

**Campo explorável × campo LAG/adaptativo** (a separação pedida para a P8):
- **Campos com perfis exploráveis** (`baseline_mixed`, `robust_mix`): o champion tem ROI claramente positivo. Isso confirma o que foi visto na P7b.
- **Campo só de adaptativos** (`adaptive_only`): o ROI cai para +33,6% [+5,8; +62,0]. Continua positivo, mas bem menor.
- **Campo de blefadores** (`bluff_heavy`): ROI de −1,8% [−28,0; +27,6], inconclusivo. **Esse é o ponto fraco mais claro do champion.** Assumir mais blefes (β = 0,2) também não ajudou: −0,104 [−0,393; +0,185].
- **Self-play** (`selfplay_hybrid`): todos os candidatos ficam perto de "campo igual" ou abaixo dele, como esperado quando o campo é parecido com o próprio agente.

**Champion × LAG de referência** (LAG − hybrid_v1): inconclusivo em todos os cenários. Não há evidência de que um supere o outro, mas também não há evidência de que sejam equivalentes.

| cenário | LAG − hybrid_v1 | IC 95% | n | relevância |
|---|---|---|---|---|
| robust_mix | -0.093 | [-0.390; +0.188] | 400 | inconclusivo |
| adaptive_only | +0.076 | [-0.262; +0.425] | 200 | inconclusivo |
| bluff_heavy | +0.109 | [-0.251; +0.480] | 200 | inconclusivo |
| baseline_mixed | +0.322 | [-0.087; +0.715] | 200 | inconclusivo |
| selfplay_hybrid | +0.022 | [-0.393; +0.447] | 100 | inconclusivo |
| versions_mix | -0.065 | [-0.535; +0.415] | 100 | inconclusivo |

## 5. Steal e re-steal: os steals desaparecem contra adaptativos?
Tabelas completas em [`P7C_STEAL_TABLES.md`](P7C_STEAL_TABLES.md) (`scripts/p7c_steal_analysis.py`, só informação pública).

- **Os steals não desaparecem.** No cenário primário, o `hybrid_v1` rouba em 49,1% das oportunidades (CO, BTN ou SB, primeiro a entrar) e ganha sem showdown em 73,8% delas.
  - O lucro por mão de steal é de **+1,26 bb [+1,14; +1,38]**.
  - Contra defensores **adaptativos** especificamente, é de +1,25 bb [+1,04; +1,47].
- **A taxa de steal sobe da 1ª para a 2ª metade do torneio** (42% → 55%). Isso acompanha o aumento de blinds e antes, e não indica que os adversários aprenderam a punir.
- **Por dimensão** (cenário primário, `hybrid_v1`), o lucro por steal é positivo em todas as posições (BTN, CO e SB) e em todas as faixas de stack efetivo. A faixa 40bb+ é a menor: +0,96 [+0,34; +1,59].
- **O que diferencia o `hybrid_v2_adaptive`** é a resposta a um re-steal: ele **paga** 54% das vezes, contra 24% do v1, e desiste 43% contra 71%.
  - É uma **hipótese plausível** para a piora, porque pagar 3-bets com ranges de steal costuma custar caro.
  - Mas é uma associação: esta avaliação **não testou essa causa**.

## 6. Onde o champion ganha (cenário primário, bb por mão, IC 95% por bootstrap de cluster)
| dimensão | grupo | mãos | bb/mão | IC 95% (cluster) |
|---|---|---|---|---|
| position | BB | 4812 | +0.004 | [-0.162; +0.157] |
| position | BTN | 4839 | +0.451 | [+0.326; +0.570] |
| position | CO | 3669 | +0.491 | [+0.347; +0.631] |
| position | HJ | 2783 | +0.369 | [+0.218; +0.511] |
| position | SB | 4156 | +0.203 | [+0.056; +0.342] |
| position | UTG | 1385 | +0.212 | [-0.003; +0.443] |
| stack_bucket | 10-20bb | 7035 | +0.280 | [+0.204; +0.347] |
| stack_bucket | 20-40bb | 7918 | +0.347 | [+0.260; +0.437] |
| stack_bucket | 40bb+ | 4305 | +0.199 | [-0.043; +0.406] |
| stack_bucket | <10bb | 2386 | +0.249 | [+0.121; +0.365] |
| phase | early | 3148 | +0.218 | [-0.082; +0.499] |
| phase | final_table | 4251 | +0.349 | [+0.252; +0.440] |
| phase | middle | 14245 | +0.281 | [+0.218; +0.342] |

## 7. Sorte nos all-ins (cenário primário)
A sorte é medida como a diferença entre o resultado real e o EV de equity no momento do all-in. Nenhum IC exclui zero, então o resultado do champion **não** é explicado por sorte nos all-ins.

| candidato | mãos all-in | sorte média (bb/all-in) | IC 95% |
|---|---|---|---|
| hybrid_v1 | 2044 | +0.333 | [-0.083; +0.760] |
| hybrid_v1_bluffcatch | 1925 | +0.119 | [-0.321; +0.560] |
| lag | 1893 | -0.204 | [-0.668; +0.262] |
| hybrid_v2_adaptive | 1938 | +0.162 | [-0.314; +0.636] |
| pushfold_p7 | 1123 | -0.005 | [-0.612; +0.601] |

## 8. Testes de invariância (informação oculta)
`tests/agents/test_robustness_agents.py`: **8/8 passando**. Os testes:
- modelo de oponentes conta steals e folds corretamente;
- modelo de oponentes lê só o histórico da observação (varredura do código-fonte);
- os agentes novos são invariantes a cartas ocultas e futuras: as decisões são idênticas quando se trocam as cartas dos adversários, e as decisões de pré-flop e flop são idênticas quando se trocam o turn e o river que ainda vão sair (20 mãos aleatórias por agente, 2 e 6 jogadores);
- os hooks do v1 não mudaram;
- o v2 aperta o range contra resistência e usa a taxa de 3-bet observada;
- sessões completas só com ações legais.

A suíte completa do `main` tem 157 testes, todos passando.

## 9. Conclusões permitidas e não permitidas
**Permitidas**
- Dentro dos campos simulados testados, nenhuma das duas variantes melhora o `hybrid-v1`. No cenário primário, as duas pioram na estimativa pontual, e a significância não sobrevive à correção de Holm.
- O champion mantém ROI positivo contra campos com adaptativos.
- O champion é mais fraco contra campos de blefadores, onde fica inconclusivo em torno de zero.
- A vantagem de steal persiste contra defensores adaptativos.

**Não permitidas**
- Afirmar que os desafiantes são "piores" com significância corrigida.
- Afirmar que champion e LAG são "equivalentes".
- Generalizar para humanos ou outros bots.
- Afirmar qualquer coisa sobre lucro com dinheiro real.

## 10. Recomendação
**Congelar o `hybrid-v1` como champion e seguir para a P8.** O ciclo cumpriu seu objetivo: testou a robustez contra adaptativos, blefadores e self-play com um protocolo pré-registrado, e a resposta foi clara o bastante para encerrar esta linha.

Pesquisa futura, fora do escopo atual:
1. A defesa contra campos de blefadores, que é o ponto fraco identificado. Deve ser feita com uma nova hipótese, uma nova seed de desenvolvimento e outra seed final.
2. A resposta a 3-bets após steal, para verificar a hipótese da seção 5.

## Artefatos
- [`p7c_artifacts/p7c_final_report.json`](p7c_artifacts/p7c_final_report.json): relatório completo, incluindo amostras progressivas.
- [`p7c_artifacts/steal_analysis.json`](p7c_artifacts/steal_analysis.json) e [`p7c_artifacts/dev_report.json`](p7c_artifacts/dev_report.json).
- [`P7C_RESULTS_TABLES.md`](P7C_RESULTS_TABLES.md): tabelas por cenário.
- [`P7C_STEAL_TABLES.md`](P7C_STEAL_TABLES.md): tabelas de steal.
- As tabelas deste relatório são geradas por `scripts/render_p7c_decision.py` e o gráfico por `scripts/make_readme_charts.py`.
