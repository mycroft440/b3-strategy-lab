# chandelier_breakout

Familia: rompimento

## Como funciona

Rompimento com saida Chandelier/ATR e filtro opcional de volume.

## Configuracao

```text
lookback=20;atr_period=14;atr_mult=3.0;volume_window=0;volume_mult=1.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
