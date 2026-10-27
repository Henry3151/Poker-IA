# O que é heurístico e o que tem garantia teórica

| Componente | Classificação | Garantia / limitação |
|---|---|---|
| Avaliador de mãos | **Exato** | Conferido contra `treys` (0 divergências em 6.000 pares de 7 cartas + ordenação de 1.500 mãos de 5 cartas). |
| Motor NLHE (side pots, all-in curto, odd chip, antes) | **Determinístico, testado** | Regras documentadas em `ENGINE_RULES.md`; propriedades Hypothesis (conservação de fichas, ninguém ganha mais do que igualou). |
| Pot odds, EV de call, fold equity de break-even, SPR | **Fórmulas exatas** | Para *uma decisão isolada*: não modelam apostas futuras (implied/reverse implied odds). |
| Outs | **Contagem exata dada a definição** | Conta cartas que sobem a categoria **usando cartas próprias**. Não garante que a mão melhorada vença, então é limite superior de outs "limpos". Regra de 2/4 é reportada só como aproximação. |
| Equity Monte Carlo | **Estimativa com erro-padrão** | Contra mãos **aleatórias uniformes**, ou top-X% quando há raise pré-flop. Ranges reais são mais estreitos, o que é uma fonte de viés conhecida. |
| Ranges (top-X%) | **Heurística** | Ordenação por equity vs. mão aleatória (tabela medida), não por solver. |
| ICM Malmuth-Harville | **Exato para o modelo** | Conferido contra enumeração independente de permutações. O **modelo** em si é uma aproximação: ignora habilidade, posição e blinds. |
| Fase do torneio | **Heurística de rotulagem** | Limiares documentados em `strategy/icm.tournament_phase`. |
| Perfil de adversário (VPIP/PFR/AF) | **Heurística** | Só ações públicas; rótulo apenas após 30 mãos (antes disso, `unknown`). |
| RandomAgent / HeuristicAgent / perfis tag-lag-nit-station | **Baselines heurísticos** | Sem garantia de qualidade; servem de referência e de campo de adversários. |
| EquityAgent (+ICM, +adaptativo) | **Heurístico** | Usa estimativas acima com regras de decisão fixas. |
| MCCFR (external sampling) | **Garantia assintótica** | Converge para equilíbrio de Nash em jogos de soma zero para **dois jogadores**. Validado no Kuhn (valor −1/18). |
| Política push/fold treinada | **ε-equilíbrio do jogo abstrato** | Garantia vale só para o jogo: HU, SB só fold/all-in, BB só fold/call, 169 classes, tabela de equity Monte Carlo. A exploitability é medida (bb/mão). |
| PolicyAgent em MTT 6-max | **Heurístico fora do jogo abstrato** | A política é usada só nos spots SB-vs-BB, com o pote não aberto até o SB, ou BB contra shove do SB. O resto vai para o EquityAgent. **ICM é ignorado** pela política (chip-EV). |
| Jogo completo NLHE 6-max MTT | **Sem garantia** | Multi-jogador, com ICM, não é soma zero entre dois. Nenhum componente deste projeto é solução de equilíbrio do jogo completo. |
