# high_vol_breakout

Familia: rompimento_volatilidade

## Como funciona

Rompimento de maxima em regime de volatilidade elevada.

## Configuracao

```text
vol_period=63;breakout_lookback=55;min_vol=0.3
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
