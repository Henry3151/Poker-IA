# Plano de Testes e Critérios de Aceite

## Testes de domínio e motor
- baralho sem cartas duplicadas;
- distribuição e ranking de mãos;
- kickers, empates e split pots;
- ordem de ação e legalidade de apostas;
- all-in, side pots, blinds e antes;
- conservação de fichas;
- estados terminais não aceitam ações;
- seeds reproduzíveis.

## Testes de informação
- agente recebe apenas suas cartas e dados públicos;
- nenhum caminho da API de agente permite consultar o deck completo;
- dados secretos de simulação são isolados da observação;
- relatórios offline não são usados durante a decisão.

## Testes de MTT
- mesas iniciais de seis jogadores;
- mesas incompletas e balanceamento;
- blinds crescentes;
- eliminações;
- encerramento com vencedor;
- integridade de stacks ao mover participantes;
- classificação e premiação consistentes.

## Testes de treinamento
- execução curta reproduzível;
- checkpoint e retomada;
- configuração e seed registradas;
- política serializada validada;
- comparação champion/challenger;
- falha de treinamento não substitui champion.

## Testes de analytics e banco
- transações atômicas;
- chaves estrangeiras;
- migrações;
- exportações que correspondem às consultas SQL;
- notas ligadas a entidades existentes;
- Power BI recebe dados consistentes;
- dados ausentes são sinalizados, não substituídos silenciosamente.

## Critérios de aceite globais
- suíte completa executada com sucesso;
- nenhuma ação inválida em smoke test;
- nenhum vazamento de cartas ocultas;
- integridade de fichas confirmada;
- MTT completo reproduzível;
- relatório de desempenho com intervalo de confiança;
- nenhuma métrica inventada;
- documentação de limitações e comandos reais de execução.
