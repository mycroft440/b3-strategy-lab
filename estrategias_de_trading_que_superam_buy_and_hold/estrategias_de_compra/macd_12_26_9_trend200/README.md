# macd_12_26_9_trend200

Familia: tendencia

## Como funciona

MACD parametrizado com confirmacao de tendencia opcional.

## Configuracao

```text
fast=12;slow=26;signal_window=9;trend_window=200
```

## Entrada e saida

A funcao produz um sinal binario long-only. A condicao descrita acima ativa a elegibilidade de compra; quando ela deixa de ser atendida, o sinal passa a zero. Estrategias com estado mantem a posicao ate sua regra explicita de saida.

O sinal calculado no fechamento somente pode gerar negociacao na abertura seguinte.
