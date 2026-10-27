# Poker AI Tournament Lab — Pacote de Arquitetura

Este pacote contém a especificação de engenharia para desenvolver um sistema local de IA para Texas Hold'em No-Limit, mesas de seis jogadores e torneios MTT simulados com múltiplas mesas.

## Objetivo
- Treinar agentes por self-play.
- Fazer agentes tomarem decisões autonomamente em ambientes de simulação autorizados.
- Executar torneios MTT locais.
- Registrar ações, estados observáveis, resultados e eventos.
- Investigar causas prováveis de vitórias e derrotas.
- Persistir dados em banco relacional.
- Expor dados para dashboards no Microsoft Power BI.
- Manter anotações de experimentos, torneios e revisões de mãos.
- Exigir testes, reprodutibilidade e relatórios honestos de execução.

## Limite operacional
Este projeto não inclui técnicas para tornar bots indetectáveis, ocultar automação, burlar antifraude ou operar em torneios online que proíbam bots. O agente autônomo destina-se a simulações locais e ambientes que autorizem expressamente agentes automatizados.

## Conteúdo
- `docs/ARCHITECTURE.md`: arquitetura e decisões técnicas.
- `docs/DATABASE.md`: modelo relacional e retenção.
- `docs/DECISION_ANALYTICS.md`: como analisar motivos de vitórias e derrotas.
- `docs/TEST_PLAN.md`: plano de testes e critérios de aceite.
- `docs/BACKLOG.md`: fases de desenvolvimento.
- `powerbi/POWERBI_SPEC.md`: páginas, KPIs, modelo semântico e visuais.
- `schemas/schema.sql`: esquema inicial SQLite.
- `schemas/events.schema.json`: contrato ilustrativo de evento.

## Como usar
1. Extraia o ZIP dentro de um diretório de trabalho.
2. Leia a especificação em `docs/` (arquitetura, banco, testes e backlog).
3. Execute a Fase 0 primeiro e revise o relatório antes de iniciar a implementação.
4. Importe os dados analíticos para Power BI conforme `powerbi/POWERBI_SPEC.md`.

O pacote é uma especificação de projeto, não um software já implementado. Nenhum teste ou benchmark é declarado como executado.
