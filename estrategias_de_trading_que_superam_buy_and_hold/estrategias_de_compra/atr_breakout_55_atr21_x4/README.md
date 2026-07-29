# atr_breakout_55_atr21_x4

Familia: rompimento

## Como funciona

Rompimento de maxima com stop movel calculado por ATR.

## Configuracao

```text
lookback=55;atr_period=21;atr_mult=4.0;trend_window=0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
