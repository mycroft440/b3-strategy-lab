# supertrend_rsi_21_4_21

Familia: combinada

## Como funciona

SuperTrend define a direcao e um oscilador confirma entrada e saida.

## Configuracao

```text
atr_period=21;atr_mult=4.0;oscillator=rsi;oscillator_period=21;lower=45.0;upper=70.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
