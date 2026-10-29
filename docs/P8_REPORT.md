# P8: exportação Power BI e dashboard (relatório)

**Status:** concluída. A exportação é reconciliada e testada, e o kit de montagem está pronto. A montagem visual no Power BI Desktop é manual, pelo guia `powerbi/GUIA_MONTAGEM_P8.md`. Nenhum `.pbix` é gerado aqui.

## O que foi entregue
| Item | Onde |
|---|---|
| Exportador do modelo estrela, com reconciliação obrigatória | `src/poker_lab/analytics/powerbi_export.py` |
| Comando de linha | `poker-lab export powerbi [--out PASTA] [--format parquet\|csv] [--run P7c ...]` · Windows: `run_powerbi_export.bat` |
| Power Query (carga da pasta, uma consulta por tabela) | `powerbi/PowerQuery.m` |
| 49 medidas DAX (fonte única e versão `DEFINE` para criar todas de uma vez) | `powerbi/measures.dax`, `powerbi/measures_dax_query_view.dax` (gerada por `scripts/build_powerbi_kit.py`) |
| Tema (paleta segura para daltonismo) | `powerbi/theme_poker_lab.json` |
| Guia de montagem: 8 páginas, relacionamentos e valores de conferência | `powerbi/GUIA_MONTAGEM_P8.md` |
| Resumos JSON para painéis web, gerados da exportação reconciliada | `scripts/build_dashboard_datasets.py` |
| Testes | `tests/integration/test_powerbi_export.py` (7 testes) |

## Modelo
- **8 dimensões:** Run, Scenario (com `FieldClass` e a participação de cada classe de oponente), Candidate (papel na execução e decisão de promoção), FieldClass, OpponentProfile, Position, StackBucket, Phase.
- **12 tabelas de fatos:** EntryResult, HandHero, Decision, Ledger, Audit, ScenarioSummary, PairedComparison, BreakdownCI, AllinLuck, Progressive, Steal e StealByDimension.
- **ICs, p-valores e vereditos vêm prontos dos relatórios congelados.** O DAX não recalcula nenhum bootstrap; ele só filtra e exibe. As medidas de IC retornam vazio fora de um contexto de 1 cenário × 1 candidato, para nunca mostrar um IC "agregado" falso.
- **Classe do campo:**
  - explorável: tag, nit, station, aleatório;
  - agressivo: LAG, maníaco, blefadores;
  - adaptativo;
  - self-play;
  - **misto**, quando nenhuma classe ocupa 75% ou mais dos assentos. A classe é calculada da composição real dos torneios no banco, e não dos rótulos.

## Reconciliação (execução de 28/10/2026)
Cada KPI é calculado de três formas — SQL no banco, linhas exportadas e relatório congelado — e as três precisam coincidir:
- torneios, lucro, custo, prêmios, ROI e ITM por cenário × candidato;
- bb/mão e número de mãos de cada corte de posição, stack e fase;
- custo e prêmios do herói no ledger contra as inscrições.

| Execução | Verificações | Divergências |
|---|---|---|
| P7 | 307 | 0 |
| P7b | 429 | 0 |
| P7c | 247 | 0 |
| **Total** | **983** | **0** |

A exportação é gravada numa pasta temporária e só é publicada se tudo coincidir. Se houver divergência, nada é publicado e o motivo fica em `<pasta>.reconciliation_FAILED.json` (há teste para isso). Os bancos de origem são abertos somente para leitura (também há teste).

Volume exportado: cerca de 104 MB em Parquet (zstd), 46 arquivos, com 1,19 milhão de decisões e 969 mil mãos do herói.

## Privacidade da informação
A exportação de decisões contém **só** dados derivados da observação do próprio herói: ação, pote, valor a pagar, equity estimada, pot odds e componente do agente. Não há cartas, JSON de observação, cartas dos adversários nem board. Há teste que verifica o schema.

## Limitações
- O kit (Power Query, DAX, tema) foi escrito e verificado fora do Power BI Desktop. A sintaxe segue a documentação, mas a **validação visual final é sua**. O guia traz valores esperados para conferir a montagem: por exemplo, P7c / robust_mix / hybrid_v1 = ROI +76,5% [+53,3%; +100,5%].
- A exportação usa os bancos locais das avaliações. Num clone novo, é preciso rodar as avaliações antes (veja `docs/COMO_USAR.md`).
