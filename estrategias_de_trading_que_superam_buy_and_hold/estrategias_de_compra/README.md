# Estrategias de compra

Catalogo long-only usado pelo executor de combinacoes.

Total combinavel com gerenciamento de carteira: 234 estrategias.

Convencoes comuns:

- o sinal usa somente informacoes disponiveis no fechamento;
- a ordem e executada na abertura do candle seguinte;
- o gerenciamento escolhe a cesta nas datas de rebalanceamento;
- dentro da cesta designada, sinal 1 significa investido e sinal 0 significa caixa; cada mudanca e executada na abertura seguinte, sem reranquear a cesta;
- dividendos/JCP, custos e slippage ficam excluidos por padrao;
- `buy_and_hold` mantem todos os ativos elegiveis e integra a matriz; o gerenciamento continua responsavel por selecao, pesos, caixa e rebalanceamento.
