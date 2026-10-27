# Arquitetura Técnica — Poker AI Tournament Lab

## 1. Escopo
Texas Hold'em No-Limit, mesas de 6 jogadores, torneios MTT multi-table simulados localmente. O sistema treina por self-play e permite decisões automáticas dentro do simulador. Qualquer integração externa futura depende de autorização explícita do ambiente.

## 2. Princípios
1. Motor de jogo é a fonte da verdade.
2. Agentes só recebem observações permitidas e ações legais.
3. Treinamento, execução, torneio, persistência e analytics são módulos separados.
4. Experimentos são reproduzíveis por configuração e seed.
5. Toda conclusão analítica distingue fatos registrados de inferências.
6. Nenhuma vitória/derrota isolada deve ser tratada como prova de qualidade estratégica.
7. Nunca declarar testes, cobertura ou desempenho sem executar e registrar os comandos.

## 3. Componentes
- `domain`: cartas, jogadores, ações, estados, stacks, potes e histórico.
- `engine`: regras, ações legais, transições, avaliação de mãos, showdown.
- `agents`: interface comum, random, heurístico, equidade e política treinada.
- `strategy`: ranges, equidade, pot odds, sizing, modelo probabilístico de adversários.
- `tournament`: diretor MTT, mesas, blinds/antes, eliminações, balanceamento, premiação.
- `training`: self-play, MCCFR experimental, abstração, checkpoints, retomada.
- `evaluation`: benchmarks, champion/challenger, intervalos de confiança, relatórios.
- `persistence`: repositórios e banco relacional.
- `analytics`: agregações, exportações e métricas de Power BI.
- `notes`: notas manuais, revisão de mãos e hipóteses estratégicas.
- `api`/`ui`: interface local opcional; nunca contém regras de jogo.
- `cli`: interface inicial recomendada.

## 4. Stack recomendada
- Python 3.12, depois de validar compatibilidade das dependências.
- Pytest + Hypothesis.
- Pydantic para contratos.
- SQLite no MVP; migração para PostgreSQL só se houver necessidade real de concorrência multiusuário.
- Pandas ou Polars para processamento analítico.
- FastAPI para API local, após CLI funcional.
- Power BI Desktop para dashboards; o arquivo `.pbix` deve ser criado e validado no Power BI Desktop, não fingido pelo código Python.
- MCCFR como linha de pesquisa separada do motor; começar com um jogo/abstração reduzidos e baselines.

## 5. Fluxo de decisão
1. Motor produz observação limitada ao jogador.
2. Motor expõe as ações legais.
3. Agente recebe observação e ações legais.
4. Agente retorna uma ação estruturada.
5. Validador confere a ação; motor executa a transição.
6. Sistema grava evento de decisão e resultado.
7. Serviços de torneio atualizam stacks, blinds, mesa e eliminações.
8. Serviço analítico atualiza métricas ou materializa agregações.
9. Avaliador compara versões sob configurações controladas.

## 6. Interfaces sugeridas
- `Engine.new_hand(config, players, seed)`
- `Engine.get_observation(player_id)`
- `Engine.get_legal_actions(player_id)`
- `Engine.apply_action(player_id, action)`
- `Engine.is_hand_finished()`
- `Engine.get_hand_result()`
- `Agent.act(observation, legal_actions) -> Action`
- `TournamentService.run(config, agent_registry, seed) -> TournamentResult`
- `TrainingService.train(config) -> TrainingSummary`
- `EvaluationService.compare(champion, challenger, suite) -> EvaluationReport`

As assinaturas são contratos de alto nível e devem ser formalizadas com tipos após a inspeção do repositório existente.

## 7. Estrutura de diretórios
```text
poker-ai/
  pyproject.toml
  configs/
  src/poker_ai/
    domain/
    engine/
    agents/
    strategy/
    tournament/
    training/
    evaluation/
    persistence/
    analytics/
    notes/
    application/
    api/
    cli.py
  tests/
    unit/
    property/
    engine/
    tournament/
    agents/
    training/
    analytics/
    integration/
    regression/
  powerbi/
  scripts/
  artifacts/          # ignorado no Git por padrão
  docs/
```

## 8. Treinamento
Não iniciar treinamento caro antes de validar as regras e baselines.
- Fase inicial: random e heurístico.
- Depois: equidade Monte Carlo, pot odds e política de ação.
- MCCFR: protótipo em abstração documentada; medir memória, throughput e comportamento.
- Checkpoints: metadados com versão de código, config, seed, versão de schema e algoritmo.
- Champion/challenger: só promover se a melhoria for apoiada por avaliação controlada; resultados inconclusivos não promovem challenger.

## 9. Segurança e integridade
- Nunca expor cartas ocultas ao agente.
- Validar cada ação com o motor.
- Limitar tempo/memória de treino.
- Tratar checkpoints como artefatos potencialmente não confiáveis.
- Não executar código arbitrário carregado de configuração ou modelo.
- API local vinculada a localhost por padrão; sem exposição de rede sem autenticação.
- Não guardar segredos em logs.
- Não implementar evasão de detecção ou automação de plataformas que proíbam bots.

## 10. Licenças
Antes de reutilizar código de referências externas, inspecionar LICENSE, avisos e dependências. Não presumir que todos os repositórios são compatíveis. Preferir implementação própria via interfaces e documentar proveniência.
