# P9: aplicação operacional (auditoria, plano e andamento)

Este documento registra a auditoria feita antes da P9, o plano aprovado (etapas B–F) e o andamento de cada etapa. Até a etapa C, cada etapa começou depois da aprovação da anterior; a partir de 28/10/2026 (noite) o usuário autorizou concluir C–F de forma autônoma, mantendo as restrições (online desativado por padrão, sem conexão real, artefatos congelados intactos).

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
| B | Interface local, inicialização simples, linha de comando, verificações | concluída |
| C | Motor de sessão autônoma com controles, aplicado à simulação local; acompanhamento ao vivo; histórico de mãos com painel "no momento da decisão" × "revelado depois" | **concluída** |
| D | Avaliação de decisões, métricas (MTT e cash separados), controle de qualidade, recomendações transformadas em experimentos | **concluída (escopo enxuto)** |
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

## Etapa C: entregue (somente simulação local)

### Validação matemática dos limites (antes de codificar)
- Regra de parada: com *n* decisões avaliáveis e *k* prováveis erros, para quando o limite inferior unilateral de 99% (Clopper–Pearson) da taxa de erro passa de 25%, o que equivale a P(X ≥ k | p = 0,25) < 0,01 (cauda binomial exata).
- Limiares calculados e fixados em teste automático: **n = 50 → 21 erros; n = 75 → 29; n = 100 → 36**.
- **Correção registrada:** o exemplo "100 decisões e 37 erros" do plano estava errado; o limiar correto é **36** (P(X ≥ 36) = 0,0094 < 0,01 e P(X ≥ 35) = 0,0164 ≥ 0,01). O teste `test_thresholds_100_decisions_is_36_not_37` garante isso.
- Adequação: intervalo de Wilson 95% (ex.: 80/100 → 71,1% a 86,7%, valor conferido em teste).
- Regra de deterioração persistente: limite inferior de 99% acima de 20% em 3 checagens seguidas (a cada 25 decisões).
- Características operacionais (simulação, 400 decisões × 400 sessões, testadas): probabilidade de parar com taxa real de erro 10% → 0%; 20% → 1,5%; 25% → 24,7%; 30% → 80%; 35% → 99,8%; 40% → 100%.

### O que foi construído
| Módulo | Função |
|---|---|
| `lab/quality.py` | Monitor de qualidade: janela móvel (100), mínimo 50, Wilson, Clopper–Pearson 99%, regra persistente, limites técnicos (2 inválidas ou 2 exceções em 100; 3 timeouts seguidos), confirmação humana para zerar a parada |
| `lab/control.py` | Máquina de estados explícita (ocioso, autônomo, pausando, supervisionado, sincronizando, parado por qualidade, saindo após a mão, emergência, encerrado, erro) com porta de ação por época; toda transição registrada com hora, origem, destino, comando, motivo, época e ator |
| `lab/controlled_agent.py` | Envolve a política congelada: cálculo em thread separada, descarte de resultados de épocas antigas, timeout com ação segura, nunca usa a política em duas decisões ao mesmo tempo |
| `lab/assessment.py` | Classificação contra referência validada (equilíbrio push/fold heads-up do checkpoint + tabela de equity); registra referência, suposições e limitações; inconclusiva quando não há referência validada |
| `lab/store.py` | Banco novo `artifacts/lab/sessions.db` (schema v1): sessões, mãos, decisões (observação do momento), revelado (separado, após a mão) e eventos |
| `lab/session.py` | Sessão autônoma 6-max com o champion `hybrid-v1` (sha256 da política registrado e conferido ao retomar), adversários simulados, métricas bb/100 com IC por posição e por adversário, perda de EV estimada |
| `lab/manager.py` | Uma sessão ativa por vez e leitura do histórico |
| API | `POST /api/simulation/start` (exige `confirm=true`), `pause`, `resume`, `emergency`, `finish`, `ack-quality`; `GET /api/simulation/current`, `/api/sessions`, `/api/sessions/{id}`, `/api/sessions/{id}/hands`, `/api/hands/{id}` |
| Interface | Telas **Simulação** (início com confirmação, controles, progresso, qualidade, resultados, últimas decisões) e **Sessões** (histórico, mãos e visualizador "no momento da decisão" × "revelado após a mão") |
| CLI | `poker-lab sim run` (Ctrl+C = emergência), `poker-lab sessions list/show` |

### Verificações da etapa C
| Verificação | Resultado |
|---|---|
| Suíte completa | **254 testes passando** (200 anteriores + 54 novos: qualidade 19, controle 14, classificação 8, sessão 8, API 3, CLI 2) |
| ruff / mypy strict | sem erros / sem erros (79 arquivos) |
| Testes de concorrência | pausa antes, durante e depois do cálculo; pausa com envio em andamento; cliques repetidos; emergência em < 1 s; resultado após encerrar descartado; 30 intercalações aleatórias sem envio com a porta fechada |
| Informação oculta e resultado | a mesma observação gera a mesma classificação em 12 baralhos diferentes, com mãos ganhas e perdidas; observações nunca contêm cartas dos adversários |
| Artefatos congelados | `FROZEN.sha256` íntegro (73 arquivos); 32 bancos/relatórios locais com sha256 **idêntico** ao baseline da etapa B (`artifacts/lab/baseline/frozen_local_after_C.sha256`) |
| Interface (navegador headless) | Simulação e Sessões sem erros de console, incluindo celular (390 px) |

### Limitações honestas
- Só os spots heads-up de push/fold têm referência validada; numa mesa 6-max isso é uma fração pequena das decisões (ex.: ~3% numa sessão de 500 mãos). O resto é **inconclusivo** de propósito, e uma parada por qualidade pode nunca ocorrer em sessões curtas.
- A simulação usa stacks reiniciados a cada mão (formato de sessão), não um torneio completo; bb/100 de algumas centenas de mãos tem intervalo muito largo.
- Ao pausar no meio de uma mão, a mesa simulada espera; numa mesa real o servidor aplicaria seu próprio timeout (tratado na etapa E).

## Etapa D: entregue (escopo enxuto)
- `lab/analysis.py`: análise de uma sessão a partir do banco de sessões, só com informação do momento da decisão. Cobertura com referência, adequação e erros com IC de Wilson, cortes por posição e por rua, piores decisões por perda de EV estimada, padrões (spot × classe de mão × ação), motivos das inconclusivas e falhas técnicas.
- Recomendações viram **hipóteses de experimento**: "observar" abaixo de 30 ocorrências e "propor experimento" a partir disso, sempre via challenger e regra champion/challenger com seeds novas. Nada altera a política.
- Métricas de cash (sessões) e de MTT (avaliações P7–P7c) ficam separadas e a análise diz isso.
- Interface: cartão "Análise de decisões" na tela Sessões. API: `GET /api/sessions/{id}/analysis`. CLI: `poker-lab sessions analyze <id> [--out pasta]` (Markdown + JSON; recusa pastas protegidas).
- Testes (4 novos + API): contagens consistentes; **trocar o resultado das mãos e apagar as cartas reveladas não muda nenhuma classificação, padrão ou recomendação**; limiar de amostra das recomendações; relatório gravado e pasta congelada recusada.
- Fora do escopo enxuto (fica como evolução): referências para spots multiway/pós-flop, solver online e agregação entre várias sessões.
