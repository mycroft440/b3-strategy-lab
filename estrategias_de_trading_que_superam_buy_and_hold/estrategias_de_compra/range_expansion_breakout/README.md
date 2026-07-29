# range_expansion_breakout

Familia: rompimento

## Como funciona

Compra expansao de range no fechamento com stop por ATR.

## Configuracao

```text
range_mult=0.5;atr_period=14;atr_mult=3.0;trend_window=50;volume_window=20;volume_mult=1.0;max_hold=40
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
