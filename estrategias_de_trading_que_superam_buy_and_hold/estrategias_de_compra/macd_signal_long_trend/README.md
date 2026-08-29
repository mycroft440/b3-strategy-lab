# macd_signal_long_trend

Familia: tendencia

## Como funciona

MACD acima do sinal e de zero, confirmado por EMA longa.

## Configuracao

```text
fast=12;slow=26;signal_period=9;trend_period=100
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
