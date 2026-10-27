# Poker AI Tournament Lab

Laboratório local de IA para Texas Hold'em No-Limit, mesas de 6 jogadores e torneios MTT **simulados**. Tudo roda num simulador local.

**Não há conexão com nenhuma sala de poker** (veja `docs/EXECUTION_LAYER.md`), e nenhum resultado aqui é evidência de lucro com dinheiro real.

## Instalação (Windows)
1. Instale o **Python 3.12+** em https://www.python.org/downloads/ e marque "Add python.exe to PATH".
2. Dê dois cliques em `setup.bat`. Ele cria `.venv` e instala `requirements-dev.txt`.
3. `run_tests.bat` roda a suíte completa de testes.
4. `run_demo.bat` roda um MTT de 12 jogadores e grava em `artifacts\demo.db`.
5. `run_p7_evaluation.bat` faz a avaliação P7 completa (demorada: ~5.900 torneios).

## Instalação (Linux/macOS)
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && pip install -e . --no-deps
python -m pytest
python scripts/demo.py
```

## Estrutura
```
src/poker_lab/
  domain/       cartas, ações, observação (whitelist), seeds
  engine/       avaliador de mãos, motor NLHE (fonte da verdade)
  agents/       Random, Heuristic (+perfis tag/lag/nit/station), Equity (+ICM, +adaptativo), Policy (MCCFR)
  strategy/     equity Monte Carlo, ranges, pot odds/EV/outs/SPR/fold equity, ICM, modelo de oponentes
  tournament/   diretor MTT (mesas, blinds, balanceamento, reentradas, premiação)
  training/     MCCFR (external sampling), Kuhn, push/fold HU, checkpoints JSON com sha256
  evaluation/   estatística (bootstrap), métricas financeiras, protocolo, relatório
  persistence/  SQLite, migrações versionadas, backup verificado, retenção
  analytics/    all-in EV offline, métricas de decisão
  notes/        notas vinculadas a experimento/torneio/mão/decisão
  application/  casos de uso (rodar mão/torneio, treinar)
```

## Documentação
- `docs/P0_REPORT.md`: inspeção, arquitetura e contratos.
- `docs/P7_REPORT.md`: resultados quantitativos da avaliação, limitações e conclusões permitidas.
- `docs/STRATEGY_GUARANTEES.md`: o que é heurístico e o que tem garantia teórica.
- `docs/TRAINING.md`: auditoria do MCCFR e da política push/fold.
- `docs/EVALUATION_PROTOCOL.md`, `docs/FINANCIAL_METRICS.md`, `docs/MIGRATIONS.md`
- `docs/ENGINE_RULES.md`, `docs/TOURNAMENT_RULES.md`, `docs/EXECUTION_LAYER.md`

## Estado das fases
P0–P7 concluídas. P8 (Power BI), P9 (CLI/API/UI) e P10 (otimização) ainda **não iniciadas**.

## Licença e terceiros
Código próprio. `treys` (MIT) é usado **apenas nos testes**, para validar o avaliador. Os repositórios GPL/AGPL de referência não tiveram código copiado (`docs/P0_REPORT.md`).
