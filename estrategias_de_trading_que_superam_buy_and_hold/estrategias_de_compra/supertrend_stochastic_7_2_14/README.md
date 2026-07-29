# supertrend_stochastic_7_2_14

Familia: combinada

## Como funciona

SuperTrend define a direcao e um oscilador confirma entrada e saida.

## Configuracao

```text
atr_period=7;atr_mult=2.0;oscillator=stochastic;oscillator_period=14;lower=25.0;upper=80.0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
