# Estrategias de compra

Catalogo long-only usado pelo executor de combinacoes.

Total testavel: 189 estrategias.

Convencoes comuns:

- o sinal usa somente informacoes disponiveis no fechamento;
- a ordem e executada na abertura do candle seguinte;
- sinal 1 significa elegivel para compra e sinal 0 significa fora da carteira;
- dividendos/JCP, custos e slippage ficam excluidos por padrao;
- `buy_and_hold` e benchmark e nao integra as 189 estrategias testaveis.
