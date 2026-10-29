# Como usar o Poker AI Tournament Lab

Guia passo a passo para instalar, rodar, reproduzir as avaliações e **analisar** os resultados. Os passos 1 a 3 funcionam em qualquer máquina com Python 3.12. As avaliações completas (passo 4) são longas e podem ser rodadas de forma parcial.

> **Escopo.** Tudo roda num simulador local, em unidades simuladas (SIM). Nada aqui é dinheiro real, e nenhum resultado é evidência de lucro fora do simulador.

---

## Sumário
1. [Instalação](#1-instalação) · [Abrir o programa](#abrir-o-programa-interface-no-navegador) · [Linha de comando](#linha-de-comando-poker-lab)
   · [Sessões autônomas de simulação](#sessões-autônomas-de-simulação-local)
2. [Testes](#2-testes-confirme-que-está-tudo-certo)
3. [Primeiro torneio (demonstração)](#3-primeiro-torneio-demonstração)
4. [Reproduzir as avaliações (P7, P7b, P7c)](#4-reproduzir-as-avaliações)
5. [Verificar a integridade](#5-verificar-a-integridade-dos-dados)
6. [Analisar os resultados](#6-analisar-os-resultados)
7. [Dashboard no Power BI](#7-dashboard-no-power-bi)
8. [Integração experimental Open Poker (P11)](#8-integração-experimental-open-poker-p11)
9. [Problemas comuns](#9-problemas-comuns)

---

## 1. Instalação

### Windows
1. Instale o **Python 3.12 ou mais novo** em <https://www.python.org/downloads/> e marque **"Add python.exe to PATH"**.
2. Instale o **Git** em <https://git-scm.com/download/win>. Só é necessário para clonar.
3. Clone o projeto e entre na pasta:
   ```bat
   git clone https://github.com/Henry3151/Poker-IA.git
   cd Poker-IA
   ```
4. Dê dois cliques em **`setup.bat`**, ou rode-o no terminal. No PowerShell, os arquivos da pasta atual precisam de `.\` na frente: **`.\setup.bat`**. Ele cria o ambiente `.venv`, instala as dependências fixadas em `requirements-dev.txt` e instala o pacote.
   - Leva de 2 a 5 minutos.
   - A mensagem final esperada é **"Instalação concluída"**.

### Linux / macOS
```bash
git clone https://github.com/Henry3151/Poker-IA.git && cd Poker-IA
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && pip install -e . --no-deps
```

**O que vem no repositório:** código, testes, documentação, os checkpoints dos modelos (`artifacts/checkpoints/`, com sha256 em `.meta.json`) e as tabelas de equity (`artifacts/tables/`). Os **bancos de resultados** (vários GB) **não** vêm: são recriados no passo 4.

### Abrir o programa (interface no navegador)
- **Windows:** dê dois cliques em **`iniciar_lab.bat`** (no PowerShell: `.\iniciar_lab.bat`).
- **Linux/macOS:** rode `./iniciar_lab.sh`.

O programa abre o navegador em `http://127.0.0.1:<porta>/`. O servidor **só aceita conexões desta máquina** e usa um código de acesso novo a cada início, que já vai embutido no endereço aberto automaticamente. Para encerrar, feche a janela do terminal ou use `Ctrl+C`.

**Telas disponíveis**
| Tela | O que faz |
|---|---|
| **Início** | Os acessos (simulação, sessão online, sessão ativa, sessões, avaliações, análise, configurar, verificar), o champion atual, um resumo das avaliações e o indicador de estado do agente |
| **Simulação** | Inicia uma sessão autônoma local e acompanha ao vivo: progresso, controles, qualidade das decisões, bb/100 por posição e por adversário, últimas decisões |
| **Sessões** | Histórico das sessões locais, lista de mãos e visualizador de mão ("no momento da decisão" × "revelado após a mão") |
| **Histórico** | Avaliações registradas (P7, P7b, P7c) e bancos encontrados em `artifacts/`, só para consulta |
| **Análise** | ROI com IC 95% por agente (gráfico e tabela) e comparação pareada contra o champion, com p Holm e relevância, por execução e cenário. Números lidos dos relatórios congelados |
| **Configurar** | Limites de tarefas, mãos e duração, salvos em `artifacts/lab/config.json`. **Chaves, senhas e tokens são recusados** |
| **Verificar** | Python e dependências, artefatos congelados (`FROZEN.sha256`) e integridade completa de cada avaliação |

**Ainda indisponível**, e marcado na tela como tal: **sessão online, desativada** (etapa E; o primeiro teste online é sempre iniciado manualmente pelo usuário, com fichas virtuais).

### Sessões autônomas de simulação local
1. Abra a tela **Simulação**.
2. Escolha mãos, seed, stack inicial (em big blinds), ante e até 5 adversários simulados (`tag`, `lag`, `nit`, `station`, `random`, `adaptive_tag`, `adaptive_lag`, `bluffer40`, `bluffer60`, `maniac`).
3. Marque a confirmação e clique em **Iniciar sessão**. A partir daí o champion (`hybrid-v1`, política congelada; o sha256 aparece na tela) joga **sozinho**, sem pedir aprovação a cada mão.
4. Controles:

| Botão | Efeito |
|---|---|
| **Pausar bot** | Fecha a porta de ação na hora. Se havia um cálculo em andamento, o resultado é **descartado**. "Pausado (supervisionado)" só aparece quando não há mais nenhuma ação em envio; depois disso nada é enviado |
| **Retomar bot** | Confere o estado da mesa (conservação das fichas) e a política (sha256) e só então volta ao modo autônomo; decisões calculadas antes da pausa nunca são reaproveitadas |
| **Encerrar após a mão** | Termina a mão atual e encerra |
| **Parada de emergência** | Interrompe imediatamente (menos de 1 s nos testes); a mão em curso é marcada como interrompida e nada mais é enviado |

5. **Controle de qualidade.** Cada decisão do agente é classificada como *adequada*, *provável erro estratégico*, *erro técnico* ou *inconclusiva*:
   - só há referência validada para spots **heads-up de push/fold** (SB sem ninguém ter entrado, ou BB contra all-in do SB) perto dos contextos treinados (5–20 bb). Ali a decisão é comparada com o equilíbrio do checkpoint pelo EV em big blinds (adequada se perder no máximo 0,10 bb; provável erro se perder 0,50 bb ou mais; entre os dois, inconclusiva);
   - todo o resto é **inconclusivo** e fica fora da janela de qualidade: concordar com "ranges plausíveis" não basta para chamar uma decisão de correta;
   - **o resultado da mão nunca é usado** para julgar a decisão (testado);
   - janela móvel de até 100 decisões avaliáveis, mínimo de 50, checagem a cada 25. A sessão **para sozinha** se o limite inferior unilateral de 99% (Clopper–Pearson) da taxa de erro passar de 25%, ou se o limite inferior ficar acima de 20% em 3 checagens seguidas, ou ainda por falhas técnicas (2 ações inválidas ou 2 exceções em 100 decisões; 3 timeouts seguidos). Em 100 decisões, a parada exige **36 erros** ou mais;
   - para retomar após uma parada por qualidade é preciso **marcar "Revisei o relatório" e escrever uma nota**;
   - a meta de 75% de adequadas é um alvo operacional experimental, **não garantia de lucro**.
6. Em **Sessões**, clique numa sessão para ver a **análise de decisões** (cobertura com referência, adequação e erros com IC 95% de Wilson, piores decisões por perda de EV estimada, motivos das inconclusivas e hipóteses de experimento) e depois numa mão para ver cada decisão com a observação daquele momento, a classificação, o EV estimado (quando há referência), a confiança e as limitações; à direita, as cartas reveladas depois da mão.

**Como ler a análise da sessão.** Recomendações são **hipóteses**: um padrão só vira "propor experimento" com pelo menos 30 ocorrências, e o próximo passo é sempre um challenger avaliado pela regra champion/challenger com seeds novas. A política da sessão nunca é alterada automaticamente. Sessões usam formato cash (stacks reiniciados), por isso bb/100 não se mistura com ROI/ITM de torneio.

Os dados vão para um banco **novo e separado**, `artifacts/lab/sessions.db`; os bancos e relatórios das avaliações nunca são tocados. A mesma seed reproduz a mesma sessão.

### Linha de comando (`poker-lab`)
Com o ambiente ativo (`.venv\Scripts\activate` no Windows, `source .venv/bin/activate` no Linux/macOS):

| Comando | O que faz | Grava algo? |
|---|---|---|
| `poker-lab info` | Ambiente, champion, execuções e artefatos congelados | não |
| `poker-lab ui` | Abre a interface (o mesmo que `iniciar_lab.bat`) | não |
| `poker-lab runs list` | Execuções conhecidas e bancos locais | não |
| `poker-lab runs show P7c` | Resumo, decisão da regra e ROI por agente | não |
| `poker-lab runs compare P7c --scenario robust_mix` | Diferenças pareadas, IC, p Holm, relevância | não |
| `poker-lab verify P7c` · `verify --all` · `verify --frozen` | Integridade dos bancos e dos artefatos congelados | não |
| `poker-lab config show` | Limites atuais | não |
| `poker-lab export powerbi` | Exportação reconciliada (passo 7) | só em `--out`; recusa pastas protegidas |
| `poker-lab doctor` | Só o ambiente | não |
| `poker-lab sim run --hands 500 --seed 1 --yes` | Sessão autônoma local no terminal (`Ctrl+C` = parada de emergência) | só em `artifacts/lab/sessions.db` |
| `poker-lab sessions list` · `sessions show <id>` | Histórico de sessões, métricas e eventos de controle | não |
| `poker-lab sessions analyze <id> [--out pasta]` | Análise de decisões em Markdown/JSON | só em `--out`; recusa pastas protegidas |

- Todos os comandos aceitam `--json` e `--help`.
- Códigos de saída: **0** ok, **1** verificação falhou, **2** erro de uso.

## 2. Testes: confirme que está tudo certo
```bat
run_tests.bat
```
No Linux/macOS: `python -m pytest`.

**Resultado esperado:** todos os testes passam (`254 passed` no `main`). Leva cerca de 3 a 10 minutos.

A suíte cobre:
- motor NLHE, com o avaliador validado contra a `treys`;
- diretor de torneio;
- agentes, incluindo testes de que nunca veem cartas ocultas;
- MCCFR;
- estatística;
- migrações do banco;
- exportação para o Power BI;
- aplicação local: segurança do servidor, linha de comando, integridade e bancos intactos.

Verificações de qualidade opcionais: `ruff check src tests scripts` e `mypy`.

## 3. Primeiro torneio (demonstração)
```bat
run_demo.bat
```
No Linux/macOS: `python scripts/demo.py`.

Roda um MTT de 12 jogadores com agentes variados e grava em `artifacts\demo.db` (SQLite). O terminal mostra a classificação final, os prêmios e o resultado do herói. Ele mesmo avisa que um torneio só não é evidência de nada. Para abrir o banco, use qualquer visualizador SQLite, por exemplo o *DB Browser for SQLite*. A view `v_entry_financials` tem lucro, ROI e ITM por participante.

## 4. Reproduzir as avaliações
Cada avaliação tem **seeds fixas**: rodar de novo produz os mesmos torneios. Os resultados vão para `artifacts\<fase>\`.

| Fase | O que responde | Comando (Windows) | Torneios | Tempo aproximado* |
|---|---|---|---|---|
| P7 | Primeira avaliação quantitativa de todos os agentes | `run_p7_evaluation.bat` | 5.900 | 1,5–3 h |
| P7b | O `hybrid-v1` supera a política anterior? (promoção) | ver abaixo | 9.100 | 2,5–5 h |
| P7c | O champion resiste a adversários adaptativos, blefadores e self-play? | `run_p7c_evaluation.bat` | 6.000 | 1,5–3 h |

\* Em um núcleo de CPU. Com dois ou mais núcleos, use *shards* em paralelo, como mostrado abaixo.

### Rodar em paralelo (mais rápido)
Cada avaliação se divide em `n` partes independentes. Abra `n` terminais e rode um shard em cada. No final, consolide uma vez só:
```bat
:: terminal 1                                  :: terminal 2
python scripts\p7c_final.py shard 0 2          python scripts\p7c_final.py shard 1 2
:: quando os dois terminarem:
python scripts\p7c_final.py finalize 2
```
O mesmo vale para `scripts\p7b_final_eval.py` e `scripts\run_p7_evaluation.py` (este último exige um `train` antes).

- **Interrompeu?** É só rodar o mesmo comando de novo: o shard retoma de onde parou.
- Se o computador desligou no meio de um torneio, rode antes `python scripts\p7c_recover.py artifacts\p7c\final0.db`. Ele remove só os torneios incompletos (veja `docs/p7c_artifacts/INCIDENT_20261027.md`).

### Rodar uma amostra rápida
Para conhecer o fluxo sem esperar horas, use a avaliação de desenvolvimento da P7c, que é menor e tem outra seed:
```bat
python scripts\p7c_dev.py shard 0 1
python scripts\p7c_dev.py finalize 1
```

## 5. Verificar a integridade dos dados
Sempre **antes** de olhar resultados:
```bat
poker-lab verify --all --frozen
```
Ou use a tela **Verificar** do programa. O resultado esperado é **"INTEGRIDADE CONFIRMADA"** em cada execução presente e **"Artefatos congelados: íntegros"**. Nesta máquina de referência, as três avaliações levam cerca de 40 s. As verificações são:
- completude contra a escala congelada;
- pareamento de seeds (CRN);
- um herói por torneio;
- conciliação do ledger;
- conservação do dinheiro;
- zero ações inválidas;
- nenhum torneio duplicado.

Os bancos são abertos **somente para leitura**. O script antigo `python scripts\p7c_integrity.py artifacts\p7c\final.db` continua funcionando.

## 6. Analisar os resultados

### 6.1 Onde estão os números
| Arquivo | Conteúdo |
|---|---|
| `artifacts\p7c\p7c_final_report.json` | Relatório completo: ROI e IC por cenário e agente, diferenças pareadas, decisão da regra congelada, cortes por posição/stack, sorte nos all-ins |
| `artifacts\p7c\steal_analysis.json` | Steal e re-steal (`python scripts\p7c_steal_analysis.py`) |
| `docs\P7C_REPORT.md`, `docs\P7B_REPORT.md`, `docs\P7_REPORT.md` | Relatórios escritos, com conclusões permitidas e não permitidas |
| `docs\p7*_artifacts\` | Cópias versionadas dos relatórios usados na documentação |

Gerar as tabelas em Markdown:
```bat
python scripts\render_p7_tables.py artifacts\p7c\p7c_final_report.json docs\P7C_RESULTS_TABLES.md hybrid_v1
python scripts\render_p7c_decision.py
python scripts\render_p7c_steal.py
```

### 6.2 Como ler cada métrica
| Métrica | Definição | Como interpretar |
|---|---|---|
| **ROI** | lucro líquido ÷ custo (buy-in 100 + taxa 10) | Com habilidade igual, o esperado é **−9,1%** (só a taxa). Acima disso, o agente ganha do campo |
| **IC 95%** | intervalo por bootstrap sobre torneios | Mostra a incerteza. Um IC largo pede mais torneios |
| **Diferença pareada** | lucro do desafiante − lucro do champion, torneio a torneio, **com as mesmas seeds** | Elimina a maior parte da sorte de cartas; é a métrica de decisão. Unidade: buy-ins por torneio |
| **p Holm** | p-valor corrigido para vários testes ao mesmo tempo | Evita "achar" efeito por acaso entre muitos cenários. Significativo se < 0,05 |
| **Relevância prática (δ = 0,10)** | o efeito importa na prática? | **Relevante**: o IC inteiro passa de ±0,10. **Incerta**: o IC exclui 0 mas cruza ±0,10 |
| **bb/100** | big blinds ganhos a cada 100 mãos | Mostra onde o agente ganha: posição, stack, fase |
| **Sorte nos all-ins** | resultado real − EV de equity no all-in | Se o IC contém 0, o resultado não é explicado por sorte |

### 6.3 Regras para tirar conclusões
1. **Integridade primeiro.** Sem o passo 5 aprovado, não interprete nada.
2. **Inconclusivo ≠ equivalente.** Um IC que contém 0 quer dizer "não sabemos", e não "são iguais".
3. **Use a regra congelada.** A decisão de promover um agente segue a regra escrita **antes** da execução (`scripts\p7c_final.py`, docstring). Não ajuste parâmetros olhando a seed final.
4. **Amostra mínima.** Cenários com n < 200 são marcados como "amostra insuficiente": servem para explorar, não para concluir.
5. **Generalização.** Os resultados valem **contra os campos simulados testados**, e não contra humanos ou outros bots.

### 6.4 Roteiro de análise sugerido
1. **Resultado principal:** a diferença pareada no cenário primário e a decisão da regra (`champion_challenger` no JSON).
2. **Robustez:** em quais cenários a estimativa é negativa, e algum IC fica inteiramente abaixo de zero?
3. **Campo:** compare as classes **explorável × agressivo × adaptativo × self-play**. O agente só ganha de campos fracos?
4. **Onde ganha:** bb/100 por posição e stack. Ganhos concentrados em BTN/CO são esperados (vantagem posicional).
5. **Sorte:** confira se os all-ins explicam o resultado.
6. **Mecanismo:** a análise de steal mostra *por que* um agente ganha ou perde. Trate como hipótese até haver um teste específico.

## 7. Dashboard no Power BI
1. Gere a exportação reconciliada:
   ```bat
   run_powerbi_export.bat
   ```
   - Cria `artifacts\powerbi\latest\` com uma pasta por tabela, `manifest.json` (com sha256 de cada arquivo) e `reconciliation.json`.
   - **Se algum KPI divergir entre banco, arquivos e relatório, nada é publicado.**
2. No Power BI Desktop, siga **`powerbi\GUIA_MONTAGEM_P8.md`**:
   - parâmetro de pasta e função de carga (`powerbi\PowerQuery.m`);
   - relacionamentos;
   - 49 medidas com um clique (`powerbi\measures_dax_query_view.dax`);
   - tema (`powerbi\theme_poker_lab.json`);
   - 8 páginas, com os valores esperados para conferência.
3. Resumos em JSON, por exemplo para um painel web: `python scripts\build_dashboard_datasets.py` gera arquivos pequenos (ROI por cenário, comparações pareadas, cortes, steal) a partir da exportação reconciliada.

## 8. Integração experimental Open Poker (P11)
Fica no branch separado **`p11-openpoker`** e está **desativada por padrão**. Joga só com fichas virtuais, numa plataforma feita para bots. Antes de qualquer uso, leia `docs/P11_OPENPOKER.md` (branch `p11-openpoker`): configuração da chave, kill switch, limites e critérios do primeiro teste.

## 9. Problemas comuns
| Sintoma | Causa provável | Solução |
|---|---|---|
| `Rode setup.bat primeiro` | ambiente `.venv` não criado | rode `setup.bat` |
| `'setup.bat' is not recognized` no PowerShell | o PowerShell não roda arquivos da pasta atual sem `.\` | use `.\setup.bat`, `.\iniciar_lab.bat` |
| `python` não reconhecido | Python fora do PATH | reinstale marcando "Add python.exe to PATH" |
| `ModuleNotFoundError: poker_lab` | pacote não instalado | `pip install -e . --no-deps`, com o `.venv` ativo |
| Avaliação interrompida | queda de energia ou reinício | rode o mesmo comando de shard de novo (é retomável) |
| Erro de chave duplicada (`UNIQUE`) ao retomar | torneio incompleto no banco | `python scripts\p7c_recover.py <banco>` e retome |
| Exportação recusada | divergência de KPI | veja `artifacts\powerbi\latest.reconciliation_FAILED.json`; não use os dados até entender a causa |
| Disco cheio | bancos grandes (P7b ~11 GB) | apague os `shard*.db`/`final0.db` depois do `finalize`; o `final.db` consolidado é o que importa |
