# Modelo de torneio MTT (simulado)

Implementação: `src/poker_lab/tournament/director.py`.

- **Mesas**: assentos sorteados com seed, em `ceil(N/6)` mesas balanceadas. O jogo avança em *rodadas*: cada mesa com 2+ jogadores joga uma mão por rodada.
- **Blinds**: nível = `rodada // hands_per_level`. Depois do último nível configurado, os blinds sobem 1,5× por nível, para garantir término.
- **Eliminações na mesma rodada**: quem começou a mão com menos fichas termina pior; empate exato é desfeito por sorteio com seed. Não há *hand-for-hand* formal.
- **Balanceamento**: depois de cada rodada, mesas são quebradas quando os jogadores cabem em menos mesas, e o tamanho das mesas difere em no máximo 1. O jogador movido é o próximo BB da mesa maior e vai para um assento livre sorteado.
- **Botão**: avança para o próximo assento ocupado (sem regra de *dead button*).
- **Reentrada**: permitida enquanto `nível < reentry_levels` e `entradas < max_entries`. A reentrada recebe stack inicial, aumenta o prize pool e vai para a mesa com menos jogadores, ou para uma mesa nova se todas estiverem cheias.
- **Premiação**: porcentagens não crescentes que somam 100, pagas até o número de participantes. O resto do arredondamento vai para o 1º. A taxa não entra no prize pool.
- **Informação pública passada aos agentes** (`TournamentInfo`): entradas, jogadores restantes, posições pagas, prêmios, nível, fase, stack médio e stacks anônimos das outras mesas.
- **Integridade**: as fichas somadas são conferidas depois de cada mão e de cada movimento. Ao final, as colocações formam uma permutação de 1..N e o vencedor tem todas as fichas.
