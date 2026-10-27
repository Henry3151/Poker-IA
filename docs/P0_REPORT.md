# Relatório P0 — Inspeção, arquitetura e contratos

Data: 2026-10-26 (America/Sao_Paulo). Tudo abaixo foi verificado nesta sessão; nada é declarado sem execução.

## 1. Repositório e ambiente inspecionados

| Item | Resultado real |
|---|---|
| Repositório de código pré-existente | **Nenhum.** O pacote recebido contém apenas especificação (11 arquivos, 36 KB: README, 5 docs, POWERBI_SPEC, 2 documentos de planejamento, schema.sql, events.schema.json). |
| Python | `python3` = 3.13.17; `/usr/bin/python3.12` = 3.12.3 (usado como alvo, venv via `uv`). |
| SQLite | 3.45.1 (suporta `CHECK`, índices parciais, `STRICT`, JSON1). |
| Dependências instaladas em 3.12 (`uv pip install`) | pytest 9.1.1 (MIT), hypothesis 6.170.12 (MPL-2.0), pydantic 2.14.1 (MIT), numpy 2.5.4 (BSD), pyarrow 26.0.0 (Apache-2.0), pandas 3.1.0 (BSD), fastapi 0.162.0 (MIT), uvicorn 0.54.0 (BSD), typer 0.27.3 (MIT), jsonschema 4.26.0 (MIT), treys 0.1.8 (MIT), phevaluator 0.6.0 (Apache-2.0), ruff 0.17.3 (MIT), mypy 2.4.0 (MIT). Todas instalaram sem erro. |
| Power BI Desktop | **Indisponível** (ambiente Linux). Nenhum `.pbix` será gerado ou declarado validado. |

## 2. Referências externas (clonadas com `git clone --depth 1`)

| Repositório | Último commit | Licença (arquivo lido) | Utilidade / decisão |
|---|---|---|---|
| fedden/poker_ai | 2020-07-19 | GPL-3.0 (`LICENSE`) | Referência conceitual de MCCFR, clustering e motor. **Nenhum código copiado** (copyleft). |
| ishikota/PyPokerEngine | 2017-04-02 | MIT (`LICENSE.md`) | Referência de API de agente (callbacks). Inativo; não usado como dependência. |
| dickreuter/Poker | 2025-06-26 | GPL-3.0 (`license.txt`) | Bot para PokerStars/PartyPoker/GGPoker via reconhecimento de imagem e mouse. **Fora do escopo** (plataformas que proíbem bots). Nada reutilizado. |
| HarperJonesGPT/PokerGPT | 2023-12-26 | MIT (`LICENSE`) | Bot GPT-4 para PokerStars com OCR e cliques simulados. **Fora do escopo**; nada reutilizado. |
| worldveil/deuces | 2023-11-29 | MIT declarado só em `setup.py`; **sem arquivo LICENSE** | Código Python 2 (`iteritems` em `lookup.py`). Não usado; o fork `treys` (MIT, PyPI) é usado **apenas em testes** para validação cruzada do avaliador. |
| pokerth/pokerth | 2026-10-19 | AGPL-3.0 (`COPYING`) | C++/Qt; referência de regras apenas. Nada reutilizado. |

Decisão: **motor e avaliador próprios** (fonte da verdade sob nosso controle e licença), validados contra `treys` em teste.

## 3. Revisão do pacote — problemas encontrados

1. **Ordem de fases inconsistente**: `BACKLOG.md` tem P7=Analytics, P8=Champion/challenger; a especificação principal e o plano de fases têm P7=Avaliação, P8=Power BI. **Adotada a ordem da especificação principal.**
2. `DATABASE.md` cita `tables`, `hand_players`, `player_results`, `metrics_snapshots`, ausentes em `schema.sql`.
3. `schema.sql` não tem: tabela de versão de migração, `CHECK` de enums, tabela de explicações (categoria/evidência/confiança/origem), tabela de avaliações champion/challenger, cartas privadas separadas da auditoria, blinds/nível por mão, `to_call`/pote/stack efetivo por decisão (exigidos pelo Hand Review), autor/severidade/vínculo a versão de agente em notas.
4. `decisions.outcome_delta_chips` e `review_*` exigiriam `UPDATE` em tabela que deve ser append-only → resultado vai para `hand_players`, revisões para `explanations`.
5. `events.schema.json` exige `tournament_id`, mas mãos de treino/avaliação heads-up não têm torneio; falta `sequence_number`; `visibility` é opcional (deveria ser obrigatório).
6. `seed INTEGER` em SQLite é 64 bits com sinal: seeds são restritos a `0..2^63-1`.
7. MCCFR em NLHE 6-max MTT completo é inviável em Python neste escopo: protótipo em jogos reduzidos (Kuhn para validação exata; push/fold heads-up abstrato para política útil em MTT).
8. Avaliador em Python puro é lento para Monte Carlo pesado → medir em P3, otimizar em P10.

## 4. Arquitetura ajustada

Pacote `poker_lab` (não `poker_ai`, para não colidir com o pacote GPL homônimo no PyPI).

```
src/poker_lab/
  domain/       cartas, ações, observação, ações legais (tipos imutáveis)
  engine/       avaliador de mãos, HandEngine NLHE (blinds, antes, side pots, showdown), eventos
  agents/       Agent protocol, Random, Heuristic, Equity, Policy(push/fold MCCFR)
  strategy/     equidade Monte Carlo, pot odds, classes 169, ranges
  tournament/   diretor MTT, mesas, balanceamento, níveis, premiação
  training/     MCCFR genérico, Kuhn, push/fold abstrato, checkpoints
  evaluation/   duplicate matches, bootstrap IC, champion/challenger
  persistence/  migrações SQL, repositórios, recorder transacional
  analytics/    explicações, export estrela CSV/Parquet, reconciliação
  notes/        serviço de notas com validação de vínculos
  application/  casos de uso (orquestra serviços)
  api/          FastAPI localhost + páginas HTML (notas, torneios, hand review)
  cli.py        Typer
```

Fluxo de decisão: motor gera `Observation` (somente cartas próprias + estado público + `LegalActions`) → agente devolve `Action` → `engine.validate` → se inválida, registra `execution_issue` e aplica fallback (check, senão fold) → evento → persistência.

## 5. Contratos (formalizados em código na P1/P2)

- `HandEngine(players, button, blinds, ante, seed)`; `.observation(seat) -> Observation`; `.legal_actions(seat) -> LegalActions`; `.apply(seat, Action)`; `.is_finished`; `.result() -> HandResult`; `.events` (com `visibility`).
- `Action(kind: fold|check|call|bet|raise, amount: int|None)` — `amount` = total da aposta na street ("raise to").
- `LegalActions(can_fold, can_check, call_amount, min_raise_to, max_raise_to)`.
- `Agent.act(obs: Observation) -> Action`.
- `TournamentDirector(config, agents, seed).run() -> TournamentResult`.
- `train_*(config) -> TrainingSummary` com checkpoint versionado (JSON + sha256).
- `compare(champion, challenger, suite) -> EvaluationReport` com IC bootstrap e decisão.

## 6. Schema e migrações

Migração `0001_initial.sql` (aplicada por runner próprio com checksum em `schema_migrations`): `experiments, agent_versions, artifacts, tournaments, tournament_entries, tournament_events, hands, hand_players, offline_hole_cards, decisions, action_events, training_runs, evaluations, explanations, audit_issues, notes`. Regras: IDs UUID texto, timestamps UTC ISO 8601, FKs `ON`, `CHECK` de enums, índices nas chaves de busca, inserção por mão em transação única, decisões/eventos append-only, notas editáveis (`updated_at`). Cartas privadas ficam **somente** em `offline_hole_cards`, nunca em `decisions.observation_json` de outro jogador.

Retenção: `poker-lab db prune --older-than-days N` remove `action_events` e `offline_hole_cards` de mãos antigas sem notas vinculadas; agregados, decisões e resultados são mantidos. Checkpoints e bancos ficam em `artifacts/` (no `.gitignore`).

## 7. Alimentação do Power BI

`poker-lab export powerbi --format parquet|csv` gera modelo estrela em `artifacts/powerbi/` (Dim*/Fact* com chaves inteiras surrogate), `DATA_DICTIONARY.md`, `measures.dax`, e `reconciliation.json` comparando cada KPI calculado nos arquivos exportados contra SQL direto. Power BI Desktop conecta via “Obter dados → Parquet/Pasta”; atualização = reexportar + “Atualizar”.

## 8. Backlog ajustado (ordem da especificação principal)

P1 motor · P2 agentes base + runner · P3 equidade/estratégia + EquityAgent · P4 MTT · P5 banco/notas/eventos · P6 MCCFR (Kuhn + push/fold) + PolicyAgent + checkpoints · P7 avaliação/champion-challenger · P8 export Power BI + explicações · P9 CLI/API/UI + hardening · P10 profiling/otimização.

## 9. Próxima fase (P1) — comandos e aceite

```
uv venv -p 3.12 .venv && uv pip install -e ".[dev]"
pytest tests/unit tests/engine tests/property -q
```
Aceite P1: avaliador concorda com `treys` na ordenação de ≥5.000 pares aleatórios; testes de side pot, split, odd chip, all-in curto que não reabre ação, heads-up, antes; propriedade Hypothesis: conservação de fichas e terminação em milhares de mãos aleatórias; nenhuma ação ilegal aceita; seeds reproduzíveis.
