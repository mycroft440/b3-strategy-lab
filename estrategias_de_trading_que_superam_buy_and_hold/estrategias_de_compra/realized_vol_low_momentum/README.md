# realized_vol_low_momentum

Familia: regime

## Como funciona

Momentum positivo apenas em regime de volatilidade realizada controlada.

## Configuracao

```text
vol_period=63;momentum_lookback=63;max_vol=0.45
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
