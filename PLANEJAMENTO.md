# Planejamento — auditoria de realismo do backtest (2026-08-25)

## Objetivo atual

Melhorar o `b3-strategy-lab` para aproximar o backtest de uma execução real,
executar a validação correta e revisar em detalhe o primeiro colocado antes de
publicar qualquer conclusão.

## Critérios de conclusão

- [x] Repositório correto identificado e branch de trabalho criada.
- [x] Práticas corretas verificadas em fontes primárias e registradas no relatório.
- [x] Suíte final reproduzida: 275 testes aprovados.
- [x] Catálogo derivado em runtime, serializado e vinculado por SHA-256; qualquer
  divergência entre contrato e execução deve abortar.
- [x] Causalidade, preços negociáveis, custos, slippage, lotes, caixa e impostos auditados.
- [x] Universo point-in-time, ações corporativas, proventos e mudanças de ticker auditados;
  dados oficiais incompletos são bloqueadores explícitos.
- [x] Liquidez usa somente referência pré-negociação e aplica limite duro de capacidade.
- [x] Seleção implementada por walk-forward sem vazamento e por uma conta OOS contínua;
  certificação permanece bloqueada até implementar PBO/DSR/PSR.
- [x] Certificações e bloqueadores de dados/custos/eventos propagados ao gate final.
- [x] Correções implementadas com testes de regressão (275 testes aprovados).
- [x] Execução iniciada e interrompida corretamente pelo gate de eventos point-in-time;
  portanto nenhum primeiro colocado certificado foi produzido.
- [x] Supervisor crítico aprovou código/gates, com resultado financeiro bloqueado.
- [ ] Mudanças publicadas no GitHub e CI verificado.

## Estado

- **Cumprido:** acesso a `mycroft440/b3-strategy-lab`; branch
  `codex/realism-audit-20260825`; pesquisa primária; auditoria inicial do motor e
  reprodução da suíte.
- **Cumprido:** catálogo/manifesto, causalidade da liquidez, limite conservador de
  capacidade, continuidade OOS e gates de fills foram endurecidos.
- **Próximo objetivo:** obter evidência histórica completa de eventos corporativos e
  proventos para os tickers antigos que a API atual da B3 não retornou; só então
  reexecutar as 111.852 combinações e auditar o primeiro lugar trade a trade.

## Restrições de interpretação

- O catálogo atual tem 234 estratégias e 478 gestões, totalizando 111.852 pares.
  A contagem anterior de 90.820 estava obsoleta. O ranking retrospectivo continua
  sendo pesquisa de hipóteses, não estimativa de retorno ao vivo.
- O antigo campeão `gap_momentum(40,20)` não será aceito sem validação
  out-of-sample, universo point-in-time e custos/slippage explícitos.
- Um replay contrafactual não pode ser chamado de execução ou conta “exata”.
