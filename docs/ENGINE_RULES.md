# Regras do motor (fonte da verdade)

Implementação: `src/poker_lab/engine/hand.py`. Testes: `tests/engine`, `tests/property`.

- 2 a 10 jogadores, em ordem de assento; o botão é dado pelo chamador.
- **Antes**: por jogador, dinheiro morto, postado antes dos blinds. Quem não tem fichas suficientes posta o que tem e fica all-in.
- **Heads-up**: o botão posta o SB, age primeiro no pré-flop e por último no pós-flop.
- **Valor a pagar no pré-flop**: o big blind inteiro, mesmo se o BB estiver curto.
- **Aposta mínima** = BB. **Raise mínimo** = último incremento *completo*.
- **All-in curto**: não reabre a ação para quem já agiu, a menos que vários all-ins curtos somados formem um raise completo sobre o que o jogador enfrentou.
- **Fold** só é legal quando há aposta a pagar.
- **Side pots** por níveis de contribuição total. Fichas não pagas voltam ao dono (`PotAward.uncalled=True`).
- **Antes/blinds de quem desistiu** acima da contribuição de qualquer jogador vivo voltam a quem pagou. Isso só ocorre com stacks minúsculos, e a regra é: ninguém ganha mais do que igualou.
- **Split pot**: fichas ímpares vão aos vencedores em ordem de assento, a partir da esquerda do botão.
- **Showdown**: todos os vivos mostram (simplificação).
- **Baralho**: permutação semeada (`random.Random(seed)`), com burn antes de flop, turn e river.
- **Conservação de fichas**: verificada no fim de cada mão; uma violação levanta `AssertionError`.
- **Observação do agente**: só as próprias cartas, o board e o estado público (`domain/observation.py`). Os campos ficam numa whitelist testada.
