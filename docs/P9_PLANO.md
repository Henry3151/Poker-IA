# P9: aplicação operacional (auditoria, plano e andamento)

Este documento registra a auditoria feita antes da P9, o plano aprovado (etapas B–F) e o andamento de cada etapa. Cada etapa só começa depois da aprovação da anterior.

## Auditoria (28/10/2026, antes de qualquer mudança)
| Item | Estado verificado |
|---|---|
| Git | `main` em `0c193d9`, sem mudanças pendentes. `p11-openpoker` com 9 commits próprios, separado desde `58b5c0f` (sem P7c/P8); 56 testes passando nele |
| Testes no `main` | 164 passando; ruff e mypy strict sem erros |
| Bancos | P7 (3,1 GB), P7b (11 GB), P7c (9,8 GB), todos com schema v2 e em modo WAL. Integridade confirmada |
| Componentes reaproveitáveis | `run_tournament`, `play_session`, `Protocol`/`run_shard`/`build_report`, tabela `decisions` (observação, ações legais, equity, explicação, latência), `offline_hole_cards` (cartas reveladas fora da decisão), exportação Power BI, adaptador P11 (estados, token, pausa até snapshot, kill switch, limites, política `cash6max-v0`) |
| Riscos encontrados | (1) `open_db()` migra o banco ao abrir, por isso a aplicação usa só conexões somente leitura; (2) os scripts de avaliação gravam em caminhos fixos, por isso execuções novas vão sempre para pastas novas; (3) o branch P11 precisa de rebase; (4) mesa online não pode ser congelada; (5) servidor local exposto ao navegador, mitigado com loopback, token e `Host`/`Origin`; (6) autorização da plataforma por conta; (7) análise de EV dependente de modelo; (8) carga no PC |

## Decisões aprovadas
- Interface no **navegador local**, iniciada por `iniciar_lab.bat`, com servidor só em `127.0.0.1`.
- **P11 integrado ao `main` só na etapa E**, depois de rebase, revisão e todos os testes; a integração fica desativada por padrão.
- **Autonomia por padrão.** Depois do "Iniciar" confirmado, o agente joga sem aprovação a cada mão, com controles manuais: Pausar bot, Retomar bot, Parada de emergência e Encerrar sessão.
  - A pausa usa uma porta de ação com contador de época: resultados de cálculos que chegam depois da pausa são descartados.
  - Ao retomar, é preciso sincronizar e obter um snapshot consistente.
  - Tokens expirados nunca são reutilizados.
  - A tela avisa quando o servidor da plataforma ainda pode agir por timeout.
- **A política nunca muda durante a sessão.** A promoção de uma versão nova só acontece pela regra champion/challenger, com uma seed nova.

## Etapas
| Etapa | Escopo | Estado |
|---|---|---|
| A | Auditoria e desenho | concluída |
| **B** | Interface local, inicialização simples, linha de comando, verificações | **concluída, aguardando aprovação** |
| C | Motor de sessão autônoma com controles, aplicado à simulação local; acompanhamento ao vivo; histórico de mãos com painel "no momento da decisão" × "revelado depois" | aguardando |
| D | Avaliação de decisões, métricas (MTT e cash separados), controle de qualidade, recomendações transformadas em experimentos | aguardando |
| E | Integração online autorizada (fichas virtuais), com todos os testes de controle no servidor falso antes de habilitar | aguardando |
| F | Empacotamento, atalho na área de trabalho e documentação final | aguardando |

## Etapa B: entregue
- **Pacote `poker_lab.lab`:**
  - `frozen.py`: manifesto `FROZEN.sha256` (73 arquivos protegidos) e verificação;
  - `readonly.py`: conexões `mode=ro`;
  - `registry.py`: execuções conhecidas e descoberta de bancos;
  - `summary.py`: resumos lidos dos relatórios congelados;
  - `integrity.py`: integridade genérica contra o protocolo congelado;
  - `config.py`: limites validados e recusa de segredos;
  - `health.py`: checagens do ambiente;
  - `jobs.py`: uma tarefa por vez.
- **Servidor:** `poker_lab.api.server` (FastAPI) e `poker_lab.api.launch`.
  - Só em `127.0.0.1`.
  - Token aleatório por início, entregue no fragmento da URL, e por isso fora de logs e requisições.
  - Checagem de `Host`/`Origin` e limites de 32 KB por requisição e de taxa de requisições.
  - Cabeçalhos de segurança: CSP `'self'`, `X-Frame-Options`, `no-store`.
  - Nenhum endpoint grava nos bancos ou nos artefatos congelados.
  - Simulação e online respondem "indisponível".
- **Interface:** `src/poker_lab/api/static/`, em HTML/CSS/JS, sem recursos externos e sem `innerHTML`. Funciona offline, nos temas claro e escuro, e em telas de celular.
- **Linha de comando:** `poker-lab info | ui | runs list/show/compare | verify [RUN|--all] [--frozen] | config show/path | export powerbi | doctor`, com `--json` e códigos de saída 0/1/2. `export` recusa pastas protegidas.
- **Inicialização:** `iniciar_lab.bat` e `iniciar_lab.sh`.

### Verificações da etapa B
| Verificação | Resultado |
|---|---|
| Suíte completa | **200 testes passando** (164 anteriores + 36 novos) |
| ruff / mypy strict | sem erros / sem erros (76 arquivos) |
| `poker-lab verify --all --frozen` nos dados reais | P7, P7b e P7c: **integridade confirmada** em todas as checagens; 73 artefatos congelados íntegros (40 s) |
| Números exibidos × relatórios congelados | idênticos (teste automático: P7c ROI +76,5% [+53,3; +100,5]; v2 −0,248, p Holm 0,2339) |
| Bancos e relatórios locais (32 arquivos, sha256) | idênticos antes e depois da etapa |
| Interface (navegador headless) | 5 telas sem erros de console; sem rolagem horizontal a 400 px; tema escuro ok |

### Limitações conhecidas da etapa B
- A interface só consulta e verifica. Simulação, acompanhamento ao vivo, análise de decisões e online chegam nas etapas C, D e E.
- O código de acesso vale enquanto a janela do programa estiver aberta. Ao reiniciar, use o novo endereço aberto automaticamente (um favorito antigo não funciona, de propósito).
- A verificação completa de integridade lê os bancos inteiros, o que leva segundos a minutos conforme o disco.
- A interface foi testada em Chromium. No Windows, o navegador padrão abre automaticamente.
