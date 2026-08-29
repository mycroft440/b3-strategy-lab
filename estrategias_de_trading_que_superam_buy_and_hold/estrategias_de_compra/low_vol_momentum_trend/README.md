# low_vol_momentum_trend

Familia: tendencia

## Como funciona

Momentum e EMA positivos sob teto de volatilidade realizada.

## Configuracao

```text
vol_period=63;ema_period=100;momentum_lookback=63;max_vol=0.4
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
