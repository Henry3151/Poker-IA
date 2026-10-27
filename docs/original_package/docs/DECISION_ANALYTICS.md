# Análise de Decisões, Vitórias e Derrotas

## 1. Objetivo
Atribuir explicações rastreáveis a resultados sem afirmar causalidade que os dados não sustentam. Poker tem variância; perder uma mão não significa que a decisão foi ruim e vencer não significa que foi boa.

## 2. Registro por decisão
Quando disponível, gravar:
- estado público e cartas próprias do agente;
- street, posição, stacks efetivos, pote, valor para pagar;
- ações legais e ação escolhida;
- versão de política e configuração;
- equidade estimada e método/quantidade de amostras;
- pot odds e sizing;
- tempo de decisão;
- resultado da mão e resultado em fichas;
- avaliação retrospectiva, claramente rotulada como estimativa;
- identificador do experimento e seed.

Nunca registrar informação secreta dos oponentes na observação que o agente recebeu. O simulador pode manter a verdade oculta separadamente para análise pós-mão, com controles para impedir vazamento durante a decisão.

## 3. Taxonomia de explicações
- `decision_quality`: provável erro de decisão, com evidência e limitações.
- `variance`: resultado desfavorável apesar de decisão estimada razoável.
- `rule_or_engine_bug`: divergência ou erro confirmado do motor.
- `opponent_adaptation`: adversário explorou padrão repetido, se houver evidência.
- `tournament_dynamics`: pressão de blinds, stack efetivo, ICM/estrutura de prêmio simplificada ou risco de eliminação.
- `insufficient_evidence`: amostra insuficiente para classificar.
- `execution_issue`: timeout, falha de inferência ou ação inválida.

## 4. Como avaliar a decisão
- Comparar ação tomada com alternativas legais sob a mesma observação.
- Se houver um estimador de EV, registrar método, pressupostos e incerteza.
- Para análise pós-mão, usar cartas reveladas somente quando legalmente disponíveis no showdown ou para análise offline de simulação; nunca disponibilizá-las ao agente no momento da decisão.
- Separar qualidade da decisão e resultado realizado.
- Evitar rótulos categóricos como “erro comprovado” quando só existe resultado negativo.
- Revisões manuais devem registrar autor, data, hipótese e conclusão.

## 5. Análise de vitórias
Não atribuir vitória automaticamente a uma boa decisão. Mostrar decisões-chave, valor esperado estimado, variância, erros de adversários detectáveis e incerteza.

## 6. Relatórios automáticos
Cada relatório deve conter:
- resumo do torneio;
- colocação, fichas e prêmio simulado;
- mãos e decisões-chave;
- fatores observados associados ao resultado;
- distinção entre fatos, estimativas e hipóteses;
- amostra, método e limitações;
- recomendações para novos experimentos.

## 7. Anotações
A página Notes deve permitir criar notas ligadas a:
- experimento;
- versão de agente;
- torneio;
- mão;
- decisão;
- hipótese de estratégia.

Campos sugeridos: título, texto Markdown simples, tags, categoria, severidade, status (open/investigating/resolved), autor local e timestamps. Não tratar notas livres como dados confiáveis sem revisão.
