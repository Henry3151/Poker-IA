# Migrações, backup e recuperação

## Regras
- As migrações ficam em `src/poker_lab/persistence/migrations/NNNN_nome.sql`. Cada uma é aplicada em transação própria e registrada em `schema_migrations` com o sha256 do arquivo. Se um arquivo já aplicado for alterado, o runner recusa (`MigrationError`).
- **Somente migrações aditivas**: tabelas novas, colunas novas com `DEFAULT`/NULL, views, índices e *backfill* por `INSERT`. Nada é apagado ou reescrito.

| Versão | Conteúdo |
|---|---|
| 0001 | schema inicial (P5) |
| 0002 | `evaluation_runs`, `financial_ledger` (idempotente), `entry_reentries`, `decision_metrics`, view `v_entry_financials`; colunas de fee/reentrada/cenário/papel; `hands.phase` e `hands.players_remaining`; backfill do ledger para torneios antigos (taxa 0) |

## Procedimento seguro (`persistence.migration_safety.safe_migrate`)
1. Pré-checagem: `PRAGMA integrity_check = ok` e `foreign_key_check` vazio.
2. Backup online pela API de backup do SQLite em `<pasta>/backups/<db>.v<versão>.<timestamp>.db`.
3. Verificação do backup: integridade ok e contagem de linhas idêntica, tabela a tabela. Grava um manifesto `.manifest.json` com as contagens, a versão e o sha256.
4. Aplica as migrações pendentes.
5. Pós-checagem: integridade, FKs e nenhuma tabela pré-existente com menos linhas.
6. Se algo falhar: restaura o backup automaticamente, confere contra o manifesto e lança `MigrationFailed(restored=True)`.

Banco novo (vazio) não precisa de backup.

## Recuperação manual
```python
from pathlib import Path
from poker_lab.persistence.migration_safety import restore_backup
restore_backup(Path("artifacts/backups/lab.v1.<ts>.db"), Path("artifacts/lab.db"))
```
`restore_backup` recusa um backup cujo sha256 não confere com o manifesto.

## Reversão da 0002
Como a 0002 é aditiva, a reversão recomendada é restaurar o backup verificado criado antes dela. Para remover manualmente sem restaurar (SQLite ≥ 3.35):
```sql
DROP VIEW v_entry_financials; DROP TABLE decision_metrics; DROP TABLE entry_reentries; DROP TABLE financial_ledger;
ALTER TABLE hands DROP COLUMN players_remaining; ALTER TABLE hands DROP COLUMN phase;  -- (drop indexes first)
-- ... demais colunas, depois: DELETE FROM schema_migrations WHERE version = 2;
```

## Testes (tests/integration/test_migration_0002.py)
- banco novo recebe 0001+0002;
- **cópia** de um banco v1 real migra sem perder linhas, o ledger reconcilia e o original fica intocado;
- backup + manifesto + restauração, com recusa de backup adulterado;
- migração quebrada (0003 artificial) é revertida automaticamente pelo backup;
- reentradas e taxas sem dupla contagem.
