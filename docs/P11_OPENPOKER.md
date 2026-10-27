# P11: Integração experimental com Open Poker (fichas virtuais)

Status: **adaptador implementado e testado só com mensagens simuladas e servidor falso local**. Nenhuma conexão real foi feita: não há chave neste ambiente, e a rede do ambiente de desenvolvimento não alcança a plataforma. **Desativado por padrão.**

Fonte: documentação oficial lida em 2026-10-27, [docs.openpoker.ai](https://docs.openpoker.ai/) (Quickstart, Message Types, `llms-full.txt`).

## 1. Auditoria
- Repositório: branch `p11-openpoker` criado a partir de `main`, que contém toda a P7c.
- O champion de MTT `pushfold@hybrid-v1` **não** é usado online. A política online é `cash6max-v0` (seção 4). O checkpoint `pushfold-v2-ante.json` (sha256 `d3e7d9ca…`) é somente leitura.
- A plataforma é feita para bots (WebSocket + JSON) e joga com **fichas virtuais** ("no real money is involved in gameplay").
  - Existem créditos e USDC (depósito/saque), mas só para o plano Pro e para prêmios de patrocinadores.
  - O adaptador **não chama** nenhum endpoint de carteira, crédito, depósito, saque ou Pro (há teste estático).
- Proibido pelas regras da plataforma: contas múltiplas, conluio, chip dumping, soft play, manipulação de ranking. Uso previsto: **1 bot, 1 instância**.

### Diferenças entre o simulador e a plataforma
| Item | Simulador (P7–P7c) | Open Poker |
|---|---|---|
| Formato | MTT de 12 jogadores com eliminação | Mesas tipo cash 6-max (2–6); pontuação = saldo de fichas da temporada |
| Blinds/antes | Crescentes; ante a partir do nível 3 | Fixos 10/20, **sem ante** |
| Stack | 3.000 (60 bb, diminuindo) | Buy-in 1.000–5.000 (**50–250 bb**); rebuy de 1.500 com cooldown |
| ICM / push-fold | Usados | Irrelevantes (sem ICM; stacks profundos) |
| Raise | Raise-to | Raise-to, entre `min` e `max` de `valid_actions` |
| All-in | Raise até o máximo | Ação `all_in` própria; all-in curto aparece como `call` |
| Abertura | `bet` quando não há aposta | Sempre `raise` (não existe `bet`) |
| Tempo | Orçamento local | 45 s por ação, depois fold/check automático; ausência após 3 mãos perdidas |
| Idempotência | — | `turn_token` de uso único + `client_action_id` |
| Reconexão | — | Assento guardado por 120 s; `resync_request` por `table_seq`; `state_hash` |
| Limites | — | 20 mensagens/s; 10 conexões/min; flood kick com 20 inválidas em 5 s |

**Consequência para a estratégia:** o `hybrid-v1` foi validado em MTT com stacks médios/curtos e antes. Online, os stacks são profundos e não há ante: a política push/fold quase nunca é usada, e o pós-flop heurístico (a parte menos validada) domina. Os resultados online **não** são comparáveis aos do simulador sem essa ressalva.

## 2. Arquitetura (módulo isolado `src/poker_lab/integrations/openpoker/`, branch `p11-openpoker`)
| Arquivo | Função |
|---|---|
| `config.py` | Ativa só com `OPEN_POKER_ENABLED=1` + `OPEN_POKER_API_KEY`. A `ApiKey` não aparece em `repr`, `str` ou pickle, e um filtro de log mascara a chave. Guardas: buy-in 1.000–5.000; orçamento de decisão < 40 s; < 20 mensagens/s; só o endpoint oficial (ou localhost em teste); `resync_timeout_s` = 20 s; `max_resync_attempts` = 3 |
| `protocol.py` | Modelos validados das mensagens e construtores das mensagens de saída. `bet` não existe na plataforma e é recusado |
| `state.py` | Rastreador da mesa, `install_snapshot`, verificação de `state_hash`, reconciliação do pote, conversão `valid_actions` ↔ `LegalActions` e conversão da ação interna para a da plataforma |
| `client.py` | Sessão com o modelo de segurança da seção 3 |
| `policy.py` | Política **`cash6max-v0`**, separada do champion de MTT (ver seção 4) |
| `recorder.py` | Banco **separado** e versionado `artifacts/openpoker/online.db`. Ver seção 6 |
| `run.py` | Executa uma sessão com `cash6max-v0` (nunca com o `hybrid-v1`) |

O motor estratégico e o simulador não foram alterados. A integração com a Open Poker é independente da P7c: não há promoção automática e o ranking online não entra na regra de champion.

## 3. Modelo de segurança das ações
**Vínculo com o token**
- Cada ação usa exatamente um `turn_token` e um `client_action_id` (uuid5 de `hand_id` + token). Um token gera no máximo uma decisão.

**O token morre (nunca é reutilizado) quando ocorre:**
- `action_ack`;
- qualquer `action_rejected`;
- `hand_result` ou uma nova `hand_start`;
- `table_closed`;
- uma nova `your_turn` com outro token;
- um snapshot de resync com outro token.

**Reenvio só quando é comprovadamente seguro.** O payload idêntico é reenviado (a documentação diz: mesmo ID + mesmo payload = retry seguro) somente se o servidor repetir o **mesmo token**:
- na **mesma mão**;
- sem nenhum evento de mesa mais novo desde o envio;
- sem `state_hash` diferente.

Caso contrário, a ação pendente é descartada e pedimos um resync. Após uma reconexão, reenviamos só se o snapshot devolver o mesmo token pendente; se o token mudou, a ação antiga é descartada e uma nova decisão é tomada.

**Pausa até haver um snapshot consistente.** Nenhuma ação é enviada nestes casos:
- desconexão;
- `state_hash` que não confere;
- estado local impossível (mão diferente, herói fora da mão, cartas ausentes, pote que não reconcilia);
- rejeição de tipo desconhecido (`not_at_table`, `table_not_found` ou códigos futuros).

Durante a pausa, a sessão envia `resync_request`. Ela só retoma depois de aplicar `replayed_events` em ordem e instalar o `snapshot`, que é o estado final, como a documentação manda. Se isso não acontecer dentro de `resync_timeout_s` × `max_resync_attempts`, a sessão sai da mesa (`reconciliation_failed`).

**Rejeições**
| Código | Reação |
|---|---|
| `stale_turn_token`, `not_your_turn`, `stale_hand_action`, `no_hand_in_progress` | Token morto; nada é reenviado |
| `invalid_action` | Contado; com 3, a sessão para (bem abaixo do flood kick de 20 inválidas em 5 s) |
| `action_id_conflict`, `legacy_action_protocol`, `missing_action_id` | Erro nosso: a sessão para (`protocol_error:*`) |

**Saltos de `table_seq`** são normais segundo a documentação ("private/direct messages to other seats consume sequence values"). Eles são apenas contados e **não** disparam resync sozinhos.

**Conversão de ações (conservadora)**
- O intervalo interno de raise é exatamente o `[min, max]` da plataforma. Ele só vai até o all-in quando o `max` já é o all-in ou quando não existe `max`.
- `all_in` só é enviado quando o agente pede exatamente o total de all-in.
- Um raise acima do `max` da plataforma é um erro e cai no fallback seguro. O valor nunca é arredondado nem limitado em silêncio.
- O all-in curto chega como `call` e continua sendo call, limitado ao stack.
- Conjuntos de ações vazios, desconhecidos ou inconsistentes viram `UnsupportedState`.

**Fallback local × ação automática do servidor**
| Situação | O que acontece |
|---|---|
| Estado consistente, mas sem suporte (ex.: mais de 6 jogadores) | **Fallback local**: check se for legal, senão fold, enviado com o token correto |
| Agente estourou o orçamento interno (10 s) ou lançou exceção | **Fallback local**: `safe_default` legal |
| Ação interna ilegal | **Fallback local**: `safe_default` legal; a ação ilegal nunca é enviada |
| Sessão em pausa (desconexão ou divergência) | **Nada é enviado**. Se o turno vencer, o servidor faz fold, ou check quando fold não é legal, aos 45 s (comportamento documentado; o resync não reinicia o relógio) |
| Kill switch ou limite de mãos | `leave_table`; nenhuma nova ação |

**Limites:** kill switch (arquivo `STOP`), `max_hands`, 8 mensagens/s, tempo de decisão de 10 s, janela de reconexão de 100 s (dentro dos 120 s do servidor) e auto-rebuy desligado.

## 4. Política online separada do champion de MTT
- `cash6max-v0` reaproveita o código híbrido **sem ICM**.
- Ela é envolvida por `CashGamePolicy`, que recusa observações de torneio e antes. Assim, a lógica de MTT não vaza para o cash, e essa política não pode ser usada na avaliação de MTT por engano.
- **Não está validada para cash** (stacks de 50–250 bb, sem ante): o pós-flop heurístico domina. Não é champion, não é promovida e as fichas virtuais não são evidência de rentabilidade.

## 5. Informação oculta
- A observação usa só as cartas próprias, os eventos públicos e os números autoritativos (pote, call, min/max).
- `shown_cards`, cartas de outros jogadores em snapshots malformados, campos extras com cartas ou equity, e mãos anteriores nunca entram na `Observation`.
- Os testes de invariância variam essas informações e verificam que a observação e a ação ficam idênticas.

## 6. Banco de dados: por que não houve migração 0003
**Decisão:** o banco principal do simulador **não foi alterado**. Os dados online ficam em `artifacts/openpoker/online.db`, com schema próprio e versionado (`online_schema_version` = 1). Motivos:
1. A P7c estava rodando no banco do simulador.
2. Partidas cash com fichas virtuais e torneios simulados não devem se misturar nas mesmas tabelas nem nos relatórios.
3. Assim, apagar ou refazer o banco online não toca em nenhum resultado anterior.

**Se a 0003 for necessária no futuro** (por exemplo, para o Power BI unificado), o procedimento é:
1. verificar o schema atual;
2. usar `safe_migrate` (backup verificado + restauração automática em caso de falha);
3. testar antes em uma cópia do banco;
4. aplicar só tabelas novas, o que permite rollback por remoção.

**Segredos:**
- Nenhum token de autenticação vai para o banco ou para os logs.
- O `turn_token`, apesar de ser de uso único, também é guardado só como digest SHA-256; o payload gravado tem o token substituído pelo digest.
- Há testes que procuram a chave no arquivo do banco, nas mensagens e nos logs.

## 7. Incompatibilidades e lacunas encontradas na documentação
- Não existe `bet`: abrir uma aposta também é `raise` (raise-to).
- O `players[]` de `your_turn` não traz apostas por street nem o status de fold. Por isso as apostas são reconstruídas pelos eventos e reconciliadas com o `pot`.
- Não há evento documentado de postagem de blinds; os blinds são inferidos pela `hand_start` e pela regra do dealer.
- A documentação não diz se o `pot` inclui as apostas da street atual; as duas convenções são aceitas e a usada é registrada.
- O `state_hash` usa JSON compacto com chaves ordenadas em UTF-8. **O primeiro teste online deve confirmar que o hash confere**: se não conferir, o bot entra em pausa (falha segura) e `hash_mismatches` aparece nas estatísticas.
- O cold restart depende de REST (`/api/me/active-game`), que não é usado nesta etapa.

## 8. Testes (sem rede; 56 no total)
- `tests/integrations/test_openpoker.py` (18):
  - configuração e segredos;
  - parsing;
  - rastreador da mesa;
  - vazamento de `shown_cards`;
  - deduplicação;
  - estados não suportados;
  - conversão de ações;
  - compatibilidade de regras;
  - sessões com servidor falso;
  - limite de mensagens;
  - varredura estática contra endpoints de dinheiro e automação de interface gráfica.
- `tests/integrations/test_openpoker_safety.py` (38):
  - vínculo de tokens;
  - reenvio idêntico só com o mesmo token;
  - token novo descarta a ação antiga;
  - token rejeitado nunca é reutilizado;
  - repetição após evento novo não é reenviada;
  - erro de protocolo interrompe a sessão;
  - pausa por hash, pote ou mão divergente, sem ação naquele turno;
  - hash válido é aceito;
  - divergência sem recuperação encerra a sessão;
  - algoritmo de hash;
  - convenções do pote;
  - tabela de casos de `valid_actions` (só check, check/bet, fold/call, all-in curto, call maior que o stack, min = max, só all-in, max limitado, só fold);
  - conjuntos inconsistentes;
  - propriedade com Hypothesis (400 casos): a ação enviada pertence sempre ao conjunto oferecido e tem o valor exato;
  - invariância a informação oculta e futura;
  - snapshot com cartas alheias;
  - separação da política cash.

## 9. Limitações conhecidas
- Tudo foi validado só contra mensagens simuladas. O formato real de `players[]`, `snapshot.seats` e `state_hash` precisa ser confirmado no primeiro teste.
- Se o pote não reconciliar por um detalhe de formato, o bot fica em pausa e o servidor age por ele. É uma falha segura, mas a sessão fica inútil até a correção.
- Não há cold restart via REST, e o auto-rebuy fica desligado.

## 10. Configuração e primeiro teste online (fichas virtuais) — a executar por você
1. Em openpoker.ai, crie **um** bot ("Self Host") e copie a chave. Não a coloque em arquivos, chats ou capturas.
2. No Windows, dentro da pasta `poker-ai` (branch `p11-openpoker`): rode `setup.bat` (instala `websockets`) e depois `run_tests.bat` (tudo deve passar).
3. Execute `powershell -ExecutionPolicy Bypass -File run_openpoker.ps1 -MaxHands 30 -BuyIn 2000`. A chave é pedida sem eco e fica só nesse processo.
4. Para parar: `stop_openpoker.bat` (cria o kill switch) ou Ctrl+C. Apague `artifacts\openpoker\STOP` antes da próxima sessão.
5. Ao final, confira as estatísticas.
   - **Critério de sucesso:** 0 `invalid_action`, 0 `protocol_error`, 0 `hash_mismatches`, 0 `divergences`, 0 `unsupported_states`, 0 timeouts e mãos completadas.
   - O resultado em fichas **não** é critério.
6. Não altere o champion com base no ranking online e não conclua nada sobre rentabilidade a partir de fichas virtuais.
