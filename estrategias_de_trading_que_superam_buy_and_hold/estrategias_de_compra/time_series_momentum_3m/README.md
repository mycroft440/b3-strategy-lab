# time_series_momentum_3m

Familia: momentum

## Como funciona

Momentum absoluto; compara o fechamento defasado com o passado e aplica filtro de tendencia opcional.

## Configuracao

```text
lookback=63;skip=0;trend_window=0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
