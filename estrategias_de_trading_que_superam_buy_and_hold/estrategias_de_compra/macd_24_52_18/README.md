# macd_24_52_18

Familia: tendencia

## Como funciona

MACD parametrizado com confirmacao de tendencia opcional.

## Configuracao

```text
fast=24;slow=52;signal_window=18;trend_window=0
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
