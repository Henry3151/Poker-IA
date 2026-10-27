# Métricas financeiras (P7)

Todos os valores são **unidades simuladas (SIM)**, nunca dinheiro real. A fonte da verdade é a tabela `financial_ledger`. As colunas `tournament_entries.simulated_payout` e `entries_count` são cópias desnormalizadas, conferidas por `reconcile_tournament_ledger`.

| Métrica | Definição | Observações |
|---|---|---|
| **Buy-in** | Valor por entrada que vai **integralmente** para o prize pool | Linha `kind='buy_in'`, negativa, uma por entrada (1ª entrada e cada reentrada). |
| **Taxa (fee/rake)** | Valor por entrada que **não** vai para o prize pool | Linha `kind='fee'`, negativa, uma por entrada. |
| **Reentrada** | Nova entrada do mesmo participante após eliminação, permitida enquanto `nível < reentry_levels` e `entries_count < max_entries` | Cada reentrada gera exatamente um buy-in e uma fee (chave `torneio:entry:tipo:n`). |
| **Prize pool** | `buy_in × total de entradas` | A taxa fica fora. |
| **Premiação** | `payout` da colocação final, pelas porcentagens configuradas | Resto do arredondamento vai para o 1º lugar. Linha `kind='payout'`, só se > 0. |
| **Custo da participação** | `Σ (buy_in + fee)` de todas as entradas do participante | |
| **Lucro líquido** | `payout − custo` | `= SUM(amount)` no ledger. |
| **ROI agregado** | `Σ lucro / Σ custo` sobre os torneios | Métrica principal, com IC por bootstrap de razão sobre torneios. |
| **ROI médio por torneio** | média de `lucro/custo` | Reportado separadamente: pondera torneios igualmente. |
| **ITM** | fração de torneios com `payout > 0` | Reentradas não dão chances extras de ITM: uma colocação por participante. |
| **Distribuição** | quantis p5/p25/p50/p75/p95 do lucro por torneio | MTT tem cauda pesada. |
| **Drawdown máximo** | maior queda pico→vale do lucro acumulado, na ordem dos torneios (`k`) | Em unidades SIM. |

**Dupla contagem**: impossível por construção. O ledger tem `UNIQUE(idempotency_key)`, e uma segunda gravação do mesmo torneio falha em transação, sem efeito parcial (há teste para isso). Taxas nunca entram no prize pool, e reentradas incrementam `entries_count` uma única vez.

**Sanidade**: num campo de agentes idênticos, o ROI esperado é `−fee/(buy_in+fee)`. Com 100+10 isso dá −9,1%. Um ROI observado acima disso não significa lucro.

**Veredito estatístico** (`evaluation/stats.verdict`):
- `insufficient_sample` se n < 200 torneios;
- `evidence_positive` / `evidence_negative` se todo o IC 95% fica acima / abaixo de 0;
- `inconclusive` caso contrário.

Mesmo `evidence_positive` vale **apenas para o cenário simulado** contra os adversários simulados. Não é prova de rentabilidade em dinheiro real.
