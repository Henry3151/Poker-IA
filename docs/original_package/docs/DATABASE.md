# Banco de Dados e Persistência

## 1. Estratégia
Usar SQLite no MVP local. O banco guarda metadados, mãos, decisões, torneios, métricas e notas. Dados grandes (checkpoints, logs de treino volumosos) ficam em arquivos locais versionados por hash e com referências no banco. Nunca salvar todos os dados brutos de simulação sem política de retenção.

## 2. Entidades principais
- `experiments`: hipótese, configuração, algoritmo, versão de código e seed.
- `agent_versions`: versão, tipo, checkpoint, checksum, origem e estado champion/challenger.
- `tournaments`: formato, número de entradas, estrutura de blinds, premiação e seed.
- `tables`: mesas por torneio e assentos.
- `hands`: número da mão, street final, board, resultado e referência do torneio.
- `hand_players`: posição, cartas privadas do jogador em ambiente de simulação, stack inicial/final e resultado. Dados privados nunca devem entrar no payload de observação de outro agente.
- `decisions`: observação serializada sanitizada, ações legais, ação escolhida, latência, política, estimativas disponíveis e resultado posterior.
- `action_events`: sequência auditável de eventos.
- `player_results`: colocação, prêmio simulado e fichas finais.
- `metrics_snapshots`: métricas agregadas por experimento/versão.
- `notes`: anotações manuais com tags e vínculo opcional a torneio/mão/decisão.
- `artifacts`: caminho, hash, tamanho, formato e metadados de checkpoints/relatórios.

## 3. Regras de persistência
- Cada torneio, mão, decisão e experimento tem ID único.
- Datas armazenadas em UTC ISO 8601; a interface converte para horário local.
- Configuração e seed são imutáveis após iniciar um experimento.
- Usar transações para registrar conclusão de mão e atualizar stacks.
- Indexar `tournament_id`, `hand_id`, `agent_version_id`, `experiment_id`, `created_at`.
- Guardar schema versionado e migrações.
- Notas podem ser editadas; decisões e eventos históricos devem ser append-only ou corrigidos por evento compensatório.
- Incluir exportação CSV/Parquet para Power BI.
- Definir retenção e rotação de logs; separar dados brutos de agregados.
