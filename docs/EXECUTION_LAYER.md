# Camada de execução externa — estado: DESATIVADA (não implementada)

- Não existe nenhum código que se conecte a sala de poker, cliente, API externa, tela ou mouse.
- O único ambiente de execução é o **simulador local** (`engine` + `tournament`).
- Não há, neste projeto, evidência documentada de nenhuma plataforma que autorize bots autônomos com dinheiro real. Por isso nenhuma integração foi criada.
- **Fora do escopo, permanentemente**: evasão de detecção ou antifraude, ocultação de automação, contorno de termos de serviço, automação em plataformas que proíbam bots.

Requisitos mínimos antes de qualquer integração futura (só com autorização oficial documentada para a plataforma e a modalidade):
1. Documento de autorização versionado (URL/arquivo + sha256, plataforma, modalidade, validade, responsável).
2. Adaptador por API oficial; nada de scraping ou automação de interface.
3. Desativada por padrão, com kill switch.
4. Limites de exposição: buy-in máximo, número de torneios/dia, perda máxima/dia, mesas simultâneas.
5. Idempotência por ação (chave única por mão e decisão), contra envio duplicado.
6. Reconciliação contínua: stacks e saldo informados pela plataforma × estado local. Qualquer divergência para a execução com segurança e gera `audit_issue`.
7. Testes de integração contra ambiente de homologação oficial antes de habilitar.
